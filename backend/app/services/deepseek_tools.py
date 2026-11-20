"""Optional DeepSeek official APIs for search, fetch, OCR and ASR.

These endpoints live on api.deepseek.com and are independent from the chat
model endpoint, so they can be used alongside an OpenAI-compatible proxy.
"""

import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.schemas.settings import LlmSettings

DEFAULT_BASE = "https://api.deepseek.com"


class DeepSeekError(RuntimeError):
    pass


@dataclass(frozen=True)
class DeepSeekConfig:
    api_base: str
    api_key: str

    @property
    def ready(self) -> bool:
        return bool(self.api_key.strip())

    def url(self, path: str) -> str:
        base = (self.api_base or DEFAULT_BASE).strip().rstrip("/")
        if base.endswith("/v1"):
            return f"{base}{path}"
        return f"{base}/v1{path}"

    @property
    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key.strip()}"}


def resolve_config(llm: LlmSettings | None = None) -> DeepSeekConfig:
    base = (
        (llm.deepseek_api_base if llm else "")
        or os.getenv("DEEPSEEK_API_BASE", "")
        or DEFAULT_BASE
    )
    key = (llm.deepseek_api_key if llm else "") or os.getenv(
        "DEEPSEEK_API_KEY", ""
    )
    return DeepSeekConfig(api_base=base.strip(), api_key=key.strip())


def _error(response: httpx.Response) -> DeepSeekError:
    detail = response.text.strip().replace("\n", " ")[:300]
    return DeepSeekError(
        f"DeepSeek 接口返回 HTTP {response.status_code}：{detail}"
    )


def _parse_search(data: dict) -> list[dict]:
    results: list[dict] = []
    for item in data.get("results") or []:
        if not isinstance(item, dict):
            continue
        results.append(
            {
                "title": str(item.get("title") or ""),
                "url": str(item.get("url") or ""),
                "summary": str(item.get("summary") or ""),
                "snippet": str(item.get("snippet") or ""),
                "content": str(item.get("content") or ""),
                "site_name": str(item.get("site_name") or ""),
                "date": str(item.get("date") or ""),
            }
        )
    return results


async def search(
    config: DeepSeekConfig,
    query: str,
    *,
    count: int = 5,
    need_content: bool = True,
    ori_question: str = "",
) -> list[dict]:
    if not config.ready:
        raise DeepSeekError("未配置 DeepSeek API Key。")
    payload: dict = {
        "query": query[:128],
        "count": max(1, min(count, 10)),
        "need_content": need_content,
    }
    if ori_question:
        payload["ori_question"] = ori_question[:128]
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                config.url("/tools/search"),
                headers=config.headers,
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise DeepSeekError(f"DeepSeek 搜索连接失败：{exc}") from exc
    if response.status_code >= 400:
        raise _error(response)
    try:
        return _parse_search(response.json())
    except ValueError as exc:
        raise DeepSeekError("DeepSeek 搜索返回了无法解析的内容。") from exc


async def fetch_page(config: DeepSeekConfig, url: str) -> dict:
    if not config.ready:
        raise DeepSeekError("未配置 DeepSeek API Key。")
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                config.url("/tools/fetch"),
                headers=config.headers,
                json={"url": url[:8192]},
            )
    except httpx.HTTPError as exc:
        raise DeepSeekError(f"DeepSeek 抓取连接失败：{exc}") from exc
    if response.status_code >= 400:
        raise _error(response)
    try:
        data = response.json()
    except ValueError as exc:
        raise DeepSeekError("DeepSeek 抓取返回了无法解析的内容。") from exc
    return {
        "title": str(data.get("title") or ""),
        "content": str(data.get("content") or ""),
    }


def _parse_ocr(data: dict) -> list[tuple[int, str]]:
    pages = data.get("pages") or []
    parsed: list[tuple[int, str]] = []
    for index, item in enumerate(pages):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        number = int(item.get("index", index)) + 1
        parsed.append((number, text))
    return parsed


def _ocr_form(path: Path, filename: str, purpose: str) -> dict:
    return {"purpose": purpose}


async def ocr_file(
    config: DeepSeekConfig,
    path: Path,
    filename: str | None = None,
    *,
    purpose: str = "text_recognition",
) -> list[tuple[int, str]]:
    if not config.ready:
        raise DeepSeekError("未配置 DeepSeek API Key。")
    name = filename or path.name
    form = _ocr_form(path, name, purpose)
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            with path.open("rb") as handle:
                mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
                response = await client.post(
                    config.url("/tools/ocr"),
                    headers=config.headers,
                    data=form,
                    files={"file": (name, handle, mime)},
                )
    except httpx.HTTPError as exc:
        raise DeepSeekError(f"DeepSeek OCR 连接失败：{exc}") from exc
    if response.status_code >= 400:
        raise _error(response)
    try:
        pages = _parse_ocr(response.json())
    except ValueError as exc:
        raise DeepSeekError("DeepSeek OCR 返回了无法解析的内容。") from exc
    if not pages:
        raise DeepSeekError("DeepSeek OCR 没有识别出文字。")
    return pages


def ocr_file_sync(
    config: DeepSeekConfig,
    path: Path,
    filename: str | None = None,
    *,
    purpose: str = "text_recognition",
) -> list[tuple[int, str]]:
    """Blocking variant used from ingestion's parser thread."""
    if not config.ready:
        raise DeepSeekError("未配置 DeepSeek API Key。")
    name = filename or path.name
    form = _ocr_form(path, name, purpose)
    try:
        with httpx.Client(timeout=300.0) as client, path.open("rb") as handle:
            mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
            response = client.post(
                config.url("/tools/ocr"),
                headers=config.headers,
                data=form,
                files={"file": (name, handle, mime)},
            )
    except httpx.HTTPError as exc:
        raise DeepSeekError(f"DeepSeek OCR 连接失败：{exc}") from exc
    if response.status_code >= 400:
        raise _error(response)
    try:
        pages = _parse_ocr(response.json())
    except ValueError as exc:
        raise DeepSeekError("DeepSeek OCR 返回了无法解析的内容。") from exc
    if not pages:
        raise DeepSeekError("DeepSeek OCR 没有识别出文字。")
    return pages


async def transcribe_audio(
    config: DeepSeekConfig,
    path: Path,
    filename: str | None = None,
) -> str:
    if not config.ready:
        raise DeepSeekError("未配置 DeepSeek API Key。")
    name = filename or path.name
    mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            with path.open("rb") as handle:
                response = await client.post(
                    config.url("/tools/asr"),
                    headers=config.headers,
                    files={"file": (name, handle, mime)},
                )
    except httpx.HTTPError as exc:
        raise DeepSeekError(f"DeepSeek 语音识别连接失败：{exc}") from exc
    if response.status_code >= 400:
        raise _error(response)
    try:
        data = response.json()
    except ValueError as exc:
        raise DeepSeekError("DeepSeek 语音识别返回了无法解析的内容。") from exc
    text = str(data.get("text") or "").strip()
    if not text:
        raise DeepSeekError("DeepSeek 语音识别没有返回文字。")
    return text
