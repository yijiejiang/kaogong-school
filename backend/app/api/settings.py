import asyncio
import time
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from litellm import acompletion
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_db
from app.schemas.settings import (
    LlmSettings,
    ServerStatus,
    SettingsBundle,
    SettingsUpdate,
)
from app.services.settings_service import (
    llm_configured,
    load_llm_settings,
    load_profile_settings,
    save_llm_settings,
    save_profile_settings,
    to_public,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


class TestRequest(BaseModel):
    llm: LlmSettings | None = None


def _database_kind() -> str:
    url = get_settings().database_url
    if url.startswith("sqlite"):
        return "sqlite"
    if url.startswith("postgresql"):
        return "postgresql"
    return "unknown"


def _normalize_model(model: str) -> str:
    model = model.strip()
    if not model:
        return ""
    return model if "/" in model else f"openai/{model}"


def _role_model(llm: LlmSettings, role: str) -> str:
    cfg = llm.roles.get(role)
    return (cfg.model if cfg and cfg.model else llm.default_model).strip()


def _friendly_error(exc: Exception, api_key: str) -> str:
    text = str(exc)
    if api_key:
        text = text.replace(api_key, "***")
    lowered = text.lower()
    if "auth" in lowered or "api key" in lowered or "401" in lowered:
        return "鉴权失败，请检查 API Key 是否有效。"
    if "model" in lowered and ("not found" in lowered or "404" in lowered):
        return "模型不可用，请检查模型名称是否与供应商一致。"
    if "connect" in lowered or "timeout" in lowered or "timed out" in lowered:
        return "连接失败，请检查 Base URL 与网络。"
    return text[:300]


@router.get("", response_model=SettingsBundle)
async def get_settings_bundle(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: str = Query("local-user"),
) -> SettingsBundle:
    llm = await load_llm_settings(db)
    profile = await load_profile_settings(db, user_id)
    return SettingsBundle(
        llm=to_public(llm),
        profile=profile,
        server=ServerStatus(
            llm_configured=llm_configured(llm),
            database=_database_kind(),
            mock_mode=get_settings().mock_llm,
        ),
    )


@router.put("", response_model=SettingsBundle)
async def update_settings(
    payload: SettingsUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: str = Query("local-user"),
) -> SettingsBundle:
    llm = await save_llm_settings(db, payload.llm)
    profile = await save_profile_settings(db, payload.profile, user_id)
    return SettingsBundle(
        llm=to_public(llm),
        profile=profile,
        server=ServerStatus(
            llm_configured=llm_configured(llm),
            database=_database_kind(),
            mock_mode=get_settings().mock_llm,
        ),
    )


@router.post("/test")
async def test_llm(
    db: Annotated[AsyncSession, Depends(get_db)],
    payload: TestRequest | None = None,
) -> dict:
    stored = await load_llm_settings(db)
    candidate = payload.llm if payload and payload.llm else stored
    api_key = candidate.api_key.strip()
    if not api_key or "••••" in api_key:
        api_key = stored.api_key

    model = _role_model(candidate, "counselor")
    if not model:
        return {"ok": False, "error": "请先填写默认模型或辅导员模型。"}

    litellm_model = _normalize_model(model)
    started = time.perf_counter()
    try:
        response = await asyncio.wait_for(
            acompletion(
                model=litellm_model,
                api_base=candidate.api_base or None,
                api_key=api_key or None,
                messages=[{"role": "user", "content": "只回复：OK"}],
                max_tokens=8,
                temperature=0,
            ),
            timeout=45,
        )
        latency = int((time.perf_counter() - started) * 1000)
        sample = ""
        choices = getattr(response, "choices", None)
        if choices:
            message = getattr(choices[0], "message", None)
            if message is not None:
                sample = getattr(message, "content", "") or ""
        return {
            "ok": True,
            "model": litellm_model,
            "latency_ms": latency,
            "sample": sample.strip()[:120],
        }
    except Exception as exc:  # noqa: BLE001 - surface provider errors to the UI
        return {
            "ok": False,
            "model": litellm_model,
            "error": _friendly_error(exc, api_key),
        }
