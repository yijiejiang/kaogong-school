import asyncio
import time
from typing import Annotated
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
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
from app.services.llm import role_model_config
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
    role: str | None = None


class ModelListRequest(BaseModel):
    api_base: str = ""
    api_key: str = ""
    role: str | None = None


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


def _model_urls(api_base: str) -> list[str]:
    base = api_base.strip().rstrip("/")
    candidates = [f"{base}/models"]
    if not base.endswith(("/v1", "/v4")):
        candidates.append(f"{base}/v1/models")
    urls: list[str] = []
    for item in candidates:
        if item not in urls:
            urls.append(item)
    return urls


def _extract_models(payload: object) -> list[dict]:
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = (
            payload.get("data")
            or payload.get("models")
            or payload.get("result")
            or []
        )
    else:
        return []
    if isinstance(items, dict):
        items = items.get("data") or []
    if not isinstance(items, list):
        return []

    models: list[dict] = []
    seen: set[str] = set()
    for item in items:
        if isinstance(item, str):
            model_id = item.strip()
            owner = ""
        elif isinstance(item, dict):
            model_id = str(
                item.get("id") or item.get("name") or item.get("model") or ""
            ).strip()
            owner = str(item.get("owned_by") or item.get("provider") or "")
        else:
            continue
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        models.append({"id": model_id, "owned_by": owner})
    models.sort(key=lambda item: item["id"].lower())
    return models


@router.post("/models")
async def list_models(
    payload: ModelListRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    stored = await load_llm_settings(db)
    if payload.role:
        endpoint = role_model_config(stored, payload.role)
        api_base = payload.api_base.strip() or endpoint.api_base
        api_key = payload.api_key.strip() or endpoint.api_key
    else:
        api_base = payload.api_base.strip() or stored.api_base
        api_key = payload.api_key.strip() or stored.api_key

    if not api_base:
        raise HTTPException(status_code=400, detail="请先填写 Base URL。")
    if not api_base.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=400, detail="Base URL 必须以 http:// 或 https:// 开头。"
        )
    host = (urlparse(api_base).hostname or "").lower()
    if host in {"169.254.169.254", "metadata.google.internal", "metadata"}:
        raise HTTPException(
            status_code=400, detail="不允许访问云元数据地址。"
        )

    headers = {}
    if api_key and "••••" not in api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    elif api_key and "••••" in api_key:
        fallback = (
            role_model_config(stored, payload.role).api_key
            if payload.role
            else stored.api_key
        )
        if fallback:
            headers["Authorization"] = f"Bearer {fallback}"

    last_error = ""
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(25.0), follow_redirects=True
    ) as client:
        for url in _model_urls(api_base):
            try:
                response = await client.get(url, headers=headers)
            except httpx.HTTPError as exc:
                last_error = f"无法连接 {url}：{exc}"
                continue
            if response.status_code in (401, 403):
                raise HTTPException(
                    status_code=400,
                    detail="鉴权失败，请检查 API Key 是否有效。",
                )
            if response.status_code == 404:
                last_error = f"{url} 不存在"
                continue
            if response.status_code >= 400:
                last_error = f"{url} 返回 {response.status_code}"
                continue
            try:
                data = response.json()
            except ValueError:
                last_error = f"{url} 返回的不是 JSON"
                continue
            models = _extract_models(data)
            if models:
                return {
                    "models": models,
                    "count": len(models),
                    "base_url": url,
                }
            last_error = f"{url} 没有返回模型列表"

    raise HTTPException(
        status_code=400, detail=f"没有获取到模型列表：{last_error or '未知原因'}"
    )


@router.post("/test")
async def test_llm(
    db: Annotated[AsyncSession, Depends(get_db)],
    payload: TestRequest | None = None,
) -> dict:
    stored = await load_llm_settings(db)
    candidate = payload.llm if payload and payload.llm else stored
    if payload and payload.role:
        endpoint = role_model_config(candidate, payload.role)
        stored_endpoint = role_model_config(stored, payload.role)
        model = endpoint.model
        api_base = endpoint.api_base
        api_key = endpoint.api_key
        if not api_key or "••••" in api_key:
            api_key = stored_endpoint.api_key
    else:
        model = candidate.default_model.strip()
        api_base = candidate.api_base
        api_key = candidate.api_key.strip()
        if not api_key or "••••" in api_key:
            api_key = stored.api_key

    if not model:
        return {"ok": False, "error": "请先填写默认模型或该角色模型。"}

    litellm_model = _normalize_model(model)
    started = time.perf_counter()
    try:
        response = await asyncio.wait_for(
            acompletion(
                model=litellm_model,
                api_base=api_base or None,
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
