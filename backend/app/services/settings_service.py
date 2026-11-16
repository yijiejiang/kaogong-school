import json
import os
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import AppSetting
from app.schemas.settings import (
    ROLE_KEYS,
    LlmSettings,
    LlmSettingsPublic,
    ProfileSettings,
    RoleModelConfig,
)
from app.services.security import decrypt_secret, encrypt_secret, mask_secret

LLM_KEY = "llm"
PROFILE_KEY = "profile"


def profile_key(user_id: str) -> str:
    return f"profile:{user_id}"


async def _read_json(db: AsyncSession, key: str) -> dict[str, Any]:
    result = await db.execute(select(AppSetting).where(AppSetting.key == key))
    row = result.scalar_one_or_none()
    if row is None or not row.value:
        return {}
    try:
        return json.loads(row.value)
    except json.JSONDecodeError:
        return {}


async def _write_json(db: AsyncSession, key: str, value: dict[str, Any]) -> None:
    result = await db.execute(select(AppSetting).where(AppSetting.key == key))
    row = result.scalar_one_or_none()
    payload = json.dumps(value, ensure_ascii=False)
    if row is None:
        db.add(AppSetting(key=key, value=payload))
    else:
        row.value = payload
    await db.commit()


def _env_defaults() -> tuple[str, str, str]:
    cfg = get_settings()
    api_base = (
        cfg.llm_api_base
        or os.getenv("OPENAI_BASE_URL")
        or os.getenv("OPENAI_API_BASE")
        or ""
    )
    api_key = (
        cfg.llm_api_key
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
        or ""
    )
    model = cfg.llm_default_model or os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL") or ""
    return api_base, api_key, model


async def load_llm_settings(db: AsyncSession) -> LlmSettings:
    data = await _read_json(db, LLM_KEY)
    api_key = ""
    if data.get("api_key_enc"):
        api_key = decrypt_secret(data["api_key_enc"])
    elif data.get("api_key"):
        api_key = data["api_key"]

    env_base, env_key, env_model = _env_defaults()
    raw_roles = data.get("roles") or {}
    roles: dict[str, RoleModelConfig] = {}
    for role in ROLE_KEYS:
        raw = raw_roles.get(role) or {}
        roles[role] = RoleModelConfig(
            model=str(raw.get("model", "")),
            temperature=float(raw.get("temperature", 0.3)),
        )

    return LlmSettings(
        api_base=str(data.get("api_base") or env_base),
        api_key=api_key or env_key,
        default_model=str(data.get("default_model") or env_model),
        embedding_model=str(
            data.get("embedding_model")
            or get_settings().llm_embedding_model
            or os.getenv("LLM_EMBEDDING_MODEL")
            or os.getenv("OPENAI_EMBEDDING_MODEL")
            or ""
        ),
        asr_model=str(data.get("asr_model") or os.getenv("ASR_MODEL") or ""),
        input_price_per_m=float(data.get("input_price_per_m") or 0.0),
        output_price_per_m=float(data.get("output_price_per_m") or 0.0),
        roles=roles,
    )


async def load_profile_settings(
    db: AsyncSession, user_id: str = "local-user"
) -> ProfileSettings:
    data = await _read_json(db, profile_key(user_id))
    if not data and user_id == "local-user":
        data = await _read_json(db, PROFILE_KEY)
    return ProfileSettings(**data) if data else ProfileSettings()


async def save_llm_settings(db: AsyncSession, llm: LlmSettings) -> LlmSettings:
    current = await load_llm_settings(db)
    api_key = llm.api_key.strip()
    if not api_key or "••••" in api_key:
        api_key = current.api_key

    payload = {
        "api_base": llm.api_base.strip(),
        "api_key_enc": encrypt_secret(api_key),
        "default_model": llm.default_model.strip(),
        "embedding_model": llm.embedding_model.strip(),
        "asr_model": llm.asr_model.strip(),
        "input_price_per_m": llm.input_price_per_m,
        "output_price_per_m": llm.output_price_per_m,
        "roles": {role: cfg.model_dump() for role, cfg in llm.roles.items()},
    }
    await _write_json(db, LLM_KEY, payload)
    return LlmSettings(
        api_base=payload["api_base"],
        api_key=api_key,
        default_model=payload["default_model"],
        embedding_model=payload["embedding_model"],
        asr_model=payload["asr_model"],
        input_price_per_m=payload["input_price_per_m"],
        output_price_per_m=payload["output_price_per_m"],
        roles=llm.roles,
    )


async def save_profile_settings(
    db: AsyncSession, profile: ProfileSettings, user_id: str = "local-user"
) -> ProfileSettings:
    await _write_json(db, profile_key(user_id), profile.model_dump())
    return profile


def llm_configured(llm: LlmSettings) -> bool:
    if get_settings().mock_llm:
        return True
    return bool(llm.default_model.strip() or any(cfg.model.strip() for cfg in llm.roles.values()))


def to_public(llm: LlmSettings) -> LlmSettingsPublic:
    return LlmSettingsPublic(
        api_base=llm.api_base,
        api_key=mask_secret(llm.api_key),
        api_key_set=bool(llm.api_key),
        default_model=llm.default_model,
        embedding_model=llm.embedding_model,
        asr_model=llm.asr_model,
        input_price_per_m=llm.input_price_per_m,
        output_price_per_m=llm.output_price_per_m,
        roles=llm.roles,
    )
