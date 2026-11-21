"""LLM token usage recording and cost summaries."""

import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LlmUsage
from app.schemas.settings import ROLE_LABELS, LlmSettings
from app.services.pricing import (
    DEEPSEEK_SERVICE_LABEL,
    MODES,
    apply_mode,
    default_mode,
    llm_cost,
    provider_from_base,
    provider_label,
    resolve_mode,
    service_cost,
)


def _llm_provider_base(llm: LlmSettings) -> str:
    return llm.api_base or ""


def estimate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    llm: LlmSettings,
    *,
    model: str = "",
    api_base: str = "",
) -> tuple[float, str, str, str]:
    """Return (cost, provider, billing_mode, note)."""
    provider = provider_from_base(api_base or _llm_provider_base(llm))
    mode = resolve_mode(provider, getattr(llm, "billing", None))
    result = llm_cost(
        provider,
        model or llm.default_model,
        prompt_tokens,
        completion_tokens,
        manual_input=llm.input_price_per_m,
        manual_output=llm.output_price_per_m,
    )
    result = apply_mode(result, mode)
    return result.cost, provider, result.billing_mode, result.note


async def record_usage(
    db: AsyncSession,
    *,
    user_id: str,
    session_id: str,
    role: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    llm: LlmSettings,
    api_base: str = "",
) -> bool:
    prompt_tokens = max(int(prompt_tokens or 0), 0)
    completion_tokens = max(int(completion_tokens or 0), 0)
    if prompt_tokens == 0 and completion_tokens == 0:
        return False

    cost, provider, mode, note = estimate_cost(
        prompt_tokens,
        completion_tokens,
        llm,
        model=model,
        api_base=api_base,
    )
    db.add(
        LlmUsage(
            id=uuid.uuid4().hex,
            user_id=user_id,
            session_id=session_id,
            role=role,
            model=model,
            service="llm",
            provider=provider,
            units=0.0,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost=cost,
            billing_mode=mode,
            note=note,
        )
    )
    return True


async def record_service_usage(
    db: AsyncSession,
    *,
    user_id: str,
    service: str,
    provider: str,
    units: float,
    llm: LlmSettings,
    model: str = "",
    note: str = "",
) -> bool:
    """Record a non-token call such as search, fetch, OCR or ASR."""
    units = max(float(units or 0), 0.0)
    if units <= 0:
        return False
    mode = resolve_mode(provider, getattr(llm, "billing", None))
    result = apply_mode(service_cost(provider, service, units), mode)
    db.add(
        LlmUsage(
            id=uuid.uuid4().hex,
            user_id=user_id,
            session_id="",
            role=service,
            model=model or service,
            service=service,
            provider=provider,
            units=units,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost=result.cost,
            billing_mode=result.billing_mode,
            note=note or result.note,
        )
    )
    return True


def _row_dict(item: LlmUsage) -> dict:
    return {
        "id": item.id,
        "role": item.role,
        "role_label": DEEPSEEK_SERVICE_LABEL.get(
            item.service if item.service != "llm" else item.role,
            ROLE_LABELS.get(item.role, item.role or "其他"),
        ),
        "model": item.model,
        "service": item.service or "llm",
        "provider": item.provider or "",
        "provider_label": provider_label(item.provider or ""),
        "units": round(item.units or 0.0, 4),
        "prompt_tokens": item.prompt_tokens,
        "completion_tokens": item.completion_tokens,
        "total_tokens": item.total_tokens,
        "cost": round(item.cost, 6),
        "billing_mode": item.billing_mode or "payg",
        "note": item.note or "",
        "created_at": item.created_at.isoformat(),
    }


async def build_usage_summary(
    db: AsyncSession, user_id: str, days: int = 14
) -> dict:
    days = max(1, min(days, 366))
    start = datetime.now(UTC) - timedelta(days=days - 1)
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    rows = list(
        (
            await db.execute(
                select(LlmUsage)
                .where(LlmUsage.user_id == user_id, LlmUsage.created_at >= start)
                .order_by(LlmUsage.created_at.desc())
            )
        ).scalars()
    )

    from app.services.settings_service import load_llm_settings

    llm = await load_llm_settings(db)
    billing = getattr(llm, "billing", None) or {}
    fallback_provider = provider_from_base(llm.api_base) if llm.api_base else "unknown"
    fallback_mode = resolve_mode(fallback_provider, billing)

    # Historical rows predate provider tracking; attribute them to the
    # currently configured endpoint and apply its billing mode.
    for item in rows:
        if not item.provider:
            item.provider = fallback_provider
            item.billing_mode = fallback_mode
            item.note = item.note or "历史记录，按当前渠道计费方式估算"
            if fallback_mode == "monthly":
                item.cost = 0.0

    prompt_tokens = sum(item.prompt_tokens for item in rows)
    completion_tokens = sum(item.completion_tokens for item in rows)
    total_tokens = prompt_tokens + completion_tokens
    cost = sum(item.cost for item in rows if (item.billing_mode or "payg") == "payg")

    by_role: dict[str, dict] = defaultdict(
        lambda: {"role": "", "role_label": "", "total_tokens": 0, "cost": 0.0}
    )
    by_model: dict[str, dict] = defaultdict(
        lambda: {"model": "", "total_tokens": 0, "cost": 0.0}
    )
    by_provider: dict[str, dict] = defaultdict(
        lambda: {
            "provider": "",
            "provider_label": "",
            "requests": 0,
            "total_tokens": 0,
            "cost": 0.0,
            "billing_modes": set(),
        }
    )
    by_service: dict[str, dict] = defaultdict(
        lambda: {"service": "", "label": "", "units": 0.0, "requests": 0, "cost": 0.0}
    )
    daily: dict[str, dict] = {
        (start + timedelta(days=offset)).date().isoformat(): {
            "date": (start + timedelta(days=offset)).date().isoformat(),
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost": 0.0,
        }
        for offset in range(days)
    }

    for item in rows:
        service = item.service or "llm"
        role_entry = by_role[item.role or "other"]
        role_entry["role"] = item.role or "other"
        role_entry["role_label"] = (
            DEEPSEEK_SERVICE_LABEL.get(service, ROLE_LABELS.get(item.role, item.role or "其他"))
            if service != "llm"
            else ROLE_LABELS.get(item.role, item.role or "其他")
        )
        role_entry["total_tokens"] += item.total_tokens
        role_entry["cost"] += item.cost

        model_entry = by_model[item.model or "unknown"]
        model_entry["model"] = item.model or "unknown"
        model_entry["total_tokens"] += item.total_tokens
        model_entry["cost"] += item.cost

        provider_key = item.provider or "unknown"
        provider_entry = by_provider[provider_key]
        provider_entry["provider"] = provider_key
        provider_entry["provider_label"] = provider_label(provider_key)
        provider_entry["requests"] += 1
        provider_entry["total_tokens"] += item.total_tokens
        provider_entry["cost"] += item.cost
        provider_entry["billing_modes"].add(item.billing_mode or "payg")

        service_entry = by_service[service]
        service_entry["service"] = service
        service_entry["label"] = DEEPSEEK_SERVICE_LABEL.get(service, service)
        service_entry["units"] += item.units or 0.0
        service_entry["requests"] += 1
        service_entry["cost"] += item.cost

        day_key = item.created_at.date().isoformat()
        if day_key in daily:
            daily[day_key]["prompt_tokens"] += item.prompt_tokens
            daily[day_key]["completion_tokens"] += item.completion_tokens
            daily[day_key]["total_tokens"] += item.total_tokens
            daily[day_key]["cost"] += item.cost

    providers = []
    for entry in by_provider.values():
        modes = sorted(entry.pop("billing_modes"))
        primary = "monthly" if modes == ["monthly"] else (modes[0] if modes else "payg")
        providers.append(
            {
                **entry,
                "cost": round(entry["cost"], 6),
                "billing_mode": primary,
                "billing_label": MODES.get(primary, primary),
            }
        )
    providers.sort(key=lambda item: item["cost"], reverse=True)

    return {
        "days": days,
        "totals": {
            "requests": len(rows),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost": round(cost, 6),
            "monthly_services": len(
                {p["provider"] for p in providers if p["billing_mode"] == "monthly"}
            ),
        },
        "by_role": sorted(
            (
                {**item, "cost": round(item["cost"], 6)}
                for item in by_role.values()
            ),
            key=lambda item: item["total_tokens"],
            reverse=True,
        ),
        "by_model": sorted(
            (
                {**item, "cost": round(item["cost"], 6)}
                for item in by_model.values()
            ),
            key=lambda item: item["total_tokens"],
            reverse=True,
        ),
        "by_provider": providers,
        "by_service": sorted(
            (
                {**item, "units": round(item["units"], 2), "cost": round(item["cost"], 6)}
                for item in by_service.values()
            ),
            key=lambda item: item["cost"],
            reverse=True,
        ),
        "daily": list(daily.values()),
        "recent": [_row_dict(item) for item in rows[:20]],
    }


async def build_billing_overview(db: AsyncSession, user_id: str) -> dict:
    """Show which providers are in use and how each is billed."""
    from app.services.settings_service import load_llm_settings

    llm = await load_llm_settings(db)
    billing = getattr(llm, "billing", None) or {}
    sources = []

    main_base = llm.api_base
    main_provider = provider_from_base(main_base)
    if main_base.strip():
        sources.append(
            {
                "provider": main_provider,
                "label": provider_label(main_provider),
                "base": main_base,
                "service": "llm",
                "model": llm.default_model,
                "billing_mode": resolve_mode(main_provider, billing),
            }
        )

    if llm.embedding_model.strip():
        embedding_provider = provider_from_base(
            llm.embedding_api_base or main_base
        )
        sources.append(
            {
                "provider": embedding_provider,
                "label": provider_label(embedding_provider),
                "base": llm.embedding_api_base or main_base,
                "service": "embedding",
                "model": llm.embedding_model,
                "billing_mode": resolve_mode(embedding_provider, billing),
            }
        )

    if llm.asr_model.strip() or llm.asr_api_base.strip():
        asr_provider = provider_from_base(llm.asr_api_base or main_base)
        sources.append(
            {
                "provider": asr_provider,
                "label": provider_label(asr_provider),
                "base": llm.asr_api_base or main_base,
                "service": "asr",
                "model": llm.asr_model,
                "billing_mode": resolve_mode(asr_provider, billing),
            }
        )

    if llm.deepseek_api_key.strip():
        sources.append(
            {
                "provider": "deepseek",
                "label": provider_label("deepseek"),
                "base": llm.deepseek_api_base or "https://api.deepseek.com",
                "service": "search/ocr/asr",
                "model": "官方工具接口",
                "billing_mode": resolve_mode("deepseek", billing),
            }
        )

    for item in sources:
        item["billing_label"] = MODES.get(item["billing_mode"], item["billing_mode"])

    return {
        "user_id": user_id,
        "default_billing": billing.get("default") or default_mode("platform"),
        "modes": [
            {"value": key, "label": label} for key, label in MODES.items()
        ],
        "sources": sources,
        "price_catalog": {
            "deepseek": {
                "currency": "CNY",
                "llm": {
                    "flash": {"peak": [2.0, 8.0], "idle": [1.0, 4.0]},
                    "pro": {"peak": [9.0, 27.0], "idle": [4.5, 13.5]},
                    "unit": "元 / 百万 tokens（输入, 输出）",
                },
                "search": "5 元 / 1,000 次",
                "fetch": "5 元 / 1,000 次",
                "ocr": "1.5 元 / 1,000 页",
                "asr": "0.39 元 / 小时（限时 5 折）",
                "tts": "3 元 / 万字符（限时 5 折 1.5 元）",
                "source": "https://api-docs.deepseek.com/zh-cn/quick_start/pricing",
            }
        },
    }
