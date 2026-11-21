import json
import logging
import re
import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.genai import types
from pydantic import BaseModel, Field

from app.agents.factory import create_root_agent
from app.config import get_settings
from app.db.session import SessionLocal
from app.schemas.settings import ROLE_KEYS, LlmSettings
from app.services.adk_runtime import RootFirstRunner, get_session_service
from app.services.llm import resolve_role_model, role_model_config
from app.services.settings_service import llm_configured, load_llm_settings
from app.services.usage import record_usage

logger = logging.getLogger(__name__)

APP_NAME = "kaogong"
router = APIRouter(prefix="/api/chat", tags=["chat"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    session_id: str | None = None
    user_id: str = "local-user"


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _event_text(event) -> str:
    if not event.content or not event.content.parts:
        return ""
    return "".join(
        part.text
        for part in event.content.parts
        if getattr(part, "text", None) and not getattr(part, "thought", False)
    )


_CJK_RE = re.compile(r"[一-鿿]")


def _clean_leading(text: str) -> str:
    """Drop an English scratchpad preamble before the first Chinese line."""
    if not text:
        return ""
    lines = text.splitlines(keepends=True)
    index = next(
        (i for i, line in enumerate(lines) if _CJK_RE.search(line)), None
    )
    if index is None or index == 0:
        return text
    leading = "".join(lines[:index])
    if len(leading) > 400:
        return text
    return "".join(lines[index:]).lstrip()


class _LeadingFilter:
    """Buffer the first chunks until the answer reaches Chinese content."""

    def __init__(self) -> None:
        self._buffers: dict[str, str] = {}
        self._released: set[str] = set()

    def feed(self, author: str, text: str, final: bool = False) -> str:
        if author in self._released:
            return text
        buffer = self._buffers.get(author, "") + text
        if _CJK_RE.search(buffer):
            self._released.add(author)
            self._buffers.pop(author, None)
            return _clean_leading(buffer)
        if final or len(buffer) > 400:
            self._released.add(author)
            self._buffers.pop(author, None)
            return buffer
        self._buffers[author] = buffer
        return ""

    def flush(self) -> list[tuple[str, str]]:
        pending = [
            (author, text)
            for author, text in self._buffers.items()
            if author not in self._released
        ]
        self._buffers.clear()
        return pending


def _event_ui(event) -> list[dict]:
    widgets: list[dict] = []
    for response in event.get_function_responses():
        data = response.response
        if isinstance(data, dict) and isinstance(data.get("ui"), dict):
            widgets.append(data["ui"])
    return widgets


def _friendly_error(exc: Exception) -> str:
    text = str(exc)
    lowered = text.lower()
    if "auth" in lowered or "api key" in lowered or "401" in lowered:
        return "LLM 鉴权失败，请到设置页检查 API Key。"
    if "model" in lowered and ("not found" in lowered or "404" in lowered):
        return "模型名称不可用，请到设置页检查模型名称。"
    if "connect" in lowered or "timeout" in lowered or "timed out" in lowered:
        return "无法连接 LLM 服务，请检查 Base URL 和网络。"
    return text[:300] or "对话失败，请稍后重试。"


async def _ensure_session(
    session_service, user_id: str, session_id: str, message: str
) -> None:
    session = await session_service.get_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    if session is None:
        await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
            state={"title": message[:40], "user_id": user_id},
        )


async def _save_usage(
    llm: LlmSettings,
    user_id: str,
    session_id: str,
    usage_by_author: dict[str, dict],
) -> None:
    try:
        async with SessionLocal() as db:
            for author, item in usage_by_author.items():
                if author not in ROLE_KEYS:
                    continue
                model = resolve_role_model(llm, author) or llm.default_model
                if get_settings().mock_llm:
                    model = model or "mock-demo"
                endpoint = role_model_config(llm, author)
                await record_usage(
                    db,
                    user_id=user_id,
                    session_id=session_id,
                    role=author,
                    model=model,
                    prompt_tokens=item["prompt_tokens"],
                    completion_tokens=item["completion_tokens"],
                    llm=llm,
                    api_base=endpoint.api_base,
                )
            await db.commit()
    except Exception:
        logger.exception("failed to persist LLM usage")


async def _stream_events(
    runner: RootFirstRunner,
    llm: LlmSettings,
    user_id: str,
    session_id: str,
    message: str,
) -> AsyncGenerator[str, None]:
    yield _sse({"type": "session", "session_id": session_id})
    streamed_authors: set[str] = set()
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    usage_by_author: dict[str, dict] = {}
    leading = _LeadingFilter()

    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(
                role="user", parts=[types.Part.from_text(text=message)]
            ),
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        ):
            transfer = getattr(event.actions, "transfer_to_agent", None)
            if transfer:
                yield _sse(
                    {"type": "transfer", "from": event.author, "to": transfer}
                )

            text = _event_text(event)
            if text:
                if event.partial:
                    text = leading.feed(event.author, text)
                    if text:
                        streamed_authors.add(event.author)
                        yield _sse(
                            {
                                "type": "delta",
                                "author": event.author,
                                "text": text,
                            }
                        )
                elif event.author in streamed_authors:
                    # The final event repeats the aggregated partial text.
                    streamed_authors.discard(event.author)
                else:
                    yield _sse(
                        {
                            "type": "message",
                            "author": event.author,
                            "text": _clean_leading(text),
                        }
                    )

            for widget in _event_ui(event):
                yield _sse(
                    {"type": "ui", "author": event.author, "component": widget}
                )

            if event.error_message:
                yield _sse({"type": "error", "message": event.error_message})

            usage_metadata = event.usage_metadata
            if usage_metadata:
                prompt_tokens = (
                    getattr(usage_metadata, "prompt_token_count", 0) or 0
                )
                completion_tokens = (
                    getattr(usage_metadata, "candidates_token_count", 0) or 0
                )
                total_tokens = (
                    getattr(usage_metadata, "total_token_count", 0) or 0
                )
                usage["prompt_tokens"] += prompt_tokens
                usage["completion_tokens"] += completion_tokens
                usage["total_tokens"] += total_tokens
                entry = usage_by_author.setdefault(
                    event.author,
                    {"prompt_tokens": 0, "completion_tokens": 0},
                )
                entry["prompt_tokens"] += prompt_tokens
                entry["completion_tokens"] += completion_tokens
    except Exception as exc:
        logger.exception("chat stream failed")
        yield _sse({"type": "error", "message": _friendly_error(exc)})
    finally:
        for author, text in leading.flush():
            yield _sse(
                {
                    "type": "message",
                    "author": author,
                    "text": _clean_leading(text),
                }
            )
        await _save_usage(llm, user_id, session_id, usage_by_author)
        yield _sse({"type": "done", "usage": usage, "session_id": session_id})


@router.post("/stream")
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    cfg = get_settings()
    user_id = req.user_id or cfg.default_user_id

    async with SessionLocal() as db:
        llm = await load_llm_settings(db)

    if not llm_configured(llm):
        async def not_configured() -> AsyncGenerator[str, None]:
            yield _sse(
                {
                    "type": "error",
                    "message": "还没有配置 LLM。请到设置页填写 Base URL、API Key 和模型。",
                }
            )
            yield _sse(
                {"type": "done", "usage": {}, "session_id": req.session_id}
            )

        return StreamingResponse(
            not_configured(), media_type="text/event-stream", headers=SSE_HEADERS
        )

    session_id = req.session_id or f"s_{uuid.uuid4().hex}"
    session_service = get_session_service()

    try:
        await _ensure_session(session_service, user_id, session_id, req.message)
        root_agent = create_root_agent(llm)
        runner = RootFirstRunner(
            agent=root_agent, app_name=APP_NAME, session_service=session_service
        )
    except Exception as exc:
        logger.exception("failed to initialise chat")
        message = _friendly_error(exc)

        async def setup_failed() -> AsyncGenerator[str, None]:
            yield _sse({"type": "error", "message": message})
            yield _sse(
                {"type": "done", "usage": {}, "session_id": session_id}
            )

        return StreamingResponse(
            setup_failed(), media_type="text/event-stream", headers=SSE_HEADERS
        )

    return StreamingResponse(
        _stream_events(runner, llm, user_id, session_id, req.message),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.get("/sessions")
async def list_sessions(user_id: str = Query("local-user")) -> list[dict]:
    service = get_session_service()
    response = await service.list_sessions(app_name=APP_NAME, user_id=user_id)
    sessions = [
        {
            "id": session.id,
            "title": (session.state or {}).get("title") or "新会话",
            "updated_at": session.last_update_time,
        }
        for session in (response.sessions or [])
    ]
    sessions.sort(key=lambda item: item.get("updated_at") or 0, reverse=True)
    return sessions


@router.get("/sessions/{session_id}/messages")
async def session_messages(
    session_id: str, user_id: str = Query("local-user")
) -> dict:
    service = get_session_service()
    session = await service.get_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    messages = []
    pending_ui: dict[str, list[tuple[dict, float]]] = {}
    for event in session.events or []:
        if event.partial:
            continue
        for widget in _event_ui(event):
            pending_ui.setdefault(event.author, []).append((widget, event.timestamp))
        text = _event_text(event)
        if not text.strip():
            continue
        text = _clean_leading(text)
        if not text.strip():
            continue
        item = {
            "id": event.id,
            "role": "user" if event.author == "user" else "assistant",
            "author": event.author,
            "content": text,
            "created_at": event.timestamp,
        }
        widgets = pending_ui.pop(event.author, [])
        if widgets:
            item["ui"] = widgets[0][0]
            for widget, timestamp in widgets[1:]:
                messages.append(
                    {
                        "id": f"ui-{uuid.uuid4().hex}",
                        "role": "assistant",
                        "author": event.author,
                        "content": "",
                        "ui": widget,
                        "created_at": timestamp,
                    }
                )
        messages.append(item)

    for author, widgets in pending_ui.items():
        for widget, timestamp in widgets:
            messages.append(
                {
                    "id": f"ui-{uuid.uuid4().hex}",
                    "role": "assistant",
                    "author": author,
                    "content": "",
                    "ui": widget,
                    "created_at": timestamp,
                }
            )

    return {"messages": messages}
