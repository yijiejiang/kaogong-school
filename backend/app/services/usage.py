"""LLM token usage recording and cost summaries."""

import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LlmUsage
from app.schemas.settings import ROLE_LABELS, LlmSettings


def estimate_cost(
    prompt_tokens: int, completion_tokens: int, llm: LlmSettings
) -> float:
    return (
        prompt_tokens / 1_000_000 * max(llm.input_price_per_m, 0.0)
        + completion_tokens / 1_000_000 * max(llm.output_price_per_m, 0.0)
    )


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
) -> bool:
    prompt_tokens = max(int(prompt_tokens or 0), 0)
    completion_tokens = max(int(completion_tokens or 0), 0)
    if prompt_tokens == 0 and completion_tokens == 0:
        return False

    db.add(
        LlmUsage(
            id=uuid.uuid4().hex,
            user_id=user_id,
            session_id=session_id,
            role=role,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost=estimate_cost(prompt_tokens, completion_tokens, llm),
        )
    )
    return True


def _row_dict(item: LlmUsage) -> dict:
    return {
        "id": item.id,
        "role": item.role,
        "role_label": ROLE_LABELS.get(item.role, item.role or "其他"),
        "model": item.model,
        "prompt_tokens": item.prompt_tokens,
        "completion_tokens": item.completion_tokens,
        "total_tokens": item.total_tokens,
        "cost": round(item.cost, 6),
        "created_at": item.created_at.isoformat(),
    }


async def build_usage_summary(
    db: AsyncSession, user_id: str, days: int = 14
) -> dict:
    days = max(1, min(days, 90))
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

    prompt_tokens = sum(item.prompt_tokens for item in rows)
    completion_tokens = sum(item.completion_tokens for item in rows)
    total_tokens = prompt_tokens + completion_tokens
    cost = sum(item.cost for item in rows)

    by_role: dict[str, dict] = defaultdict(
        lambda: {"role": "", "role_label": "", "total_tokens": 0, "cost": 0.0}
    )
    by_model: dict[str, dict] = defaultdict(
        lambda: {"model": "", "total_tokens": 0, "cost": 0.0}
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
        role_entry = by_role[item.role or "other"]
        role_entry["role"] = item.role or "other"
        role_entry["role_label"] = ROLE_LABELS.get(
            item.role, item.role or "其他"
        )
        role_entry["total_tokens"] += item.total_tokens
        role_entry["cost"] += item.cost

        model_entry = by_model[item.model or "unknown"]
        model_entry["model"] = item.model or "unknown"
        model_entry["total_tokens"] += item.total_tokens
        model_entry["cost"] += item.cost

        day_key = item.created_at.date().isoformat()
        if day_key in daily:
            daily[day_key]["prompt_tokens"] += item.prompt_tokens
            daily[day_key]["completion_tokens"] += item.completion_tokens
            daily[day_key]["total_tokens"] += item.total_tokens
            daily[day_key]["cost"] += item.cost

    return {
        "days": days,
        "totals": {
            "requests": len(rows),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost": round(cost, 6),
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
        "daily": list(daily.values()),
        "recent": [_row_dict(item) for item in rows[:12]],
    }
