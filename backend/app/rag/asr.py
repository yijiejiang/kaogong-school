"""Speech-to-text via an OpenAI-compatible audio API or local faster-whisper."""

import asyncio
import logging
import mimetypes
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx
import yt_dlp

from app.config import get_settings
from app.schemas.settings import LlmSettings
from app.services.deepseek_tools import (
    DeepSeekConfig,
    DeepSeekError,
    transcribe_audio,
)

logger = logging.getLogger(__name__)

AUDIO_SUFFIXES = {
    ".mp3",
    ".m4a",
    ".wav",
    ".aac",
    ".flac",
    ".ogg",
    ".opus",
    ".webm",
    ".mp4",
}
DEFAULT_ASR_MODEL = "whisper-1"
DEFAULT_LOCAL_MODEL = "base"


class AsrError(RuntimeError):
    """Transcription failed for a reason we can show to the user."""


class AsrUnavailable(AsrError):
    """No transcription backend is configured."""


@dataclass
class AsrResult:
    text: str
    provider: str
    model: str
    segments: list[tuple[float, float, str]] | None = None


class Transcriber(Protocol):
    async def __call__(self, url: str) -> AsrResult: ...


def resolve_asr_model(llm: LlmSettings) -> str:
    return (
        llm.asr_model.strip()
        or os.getenv("ASR_MODEL", "").strip()
        or DEFAULT_ASR_MODEL
    )


def resolve_asr_endpoint(llm: LlmSettings) -> tuple[str, str]:
    base = (llm.asr_api_base or llm.api_base).strip()
    key = (llm.asr_api_key or llm.api_key).strip()
    return base, key


def api_configured(llm: LlmSettings) -> bool:
    base, key = resolve_asr_endpoint(llm)
    return bool(base and key)


def local_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
    except Exception:  # noqa: BLE001 - optional dependency
        return False
    return True


def asr_ready(llm: LlmSettings) -> bool:
    return api_configured(llm) or local_available()


def asr_status(llm: LlmSettings) -> dict:
    return {
        "ready": asr_ready(llm),
        "api_configured": api_configured(llm),
        "local_available": local_available(),
        "model": resolve_asr_model(llm),
    }


def _audio_mime(filename: str) -> str:
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def _parse_api_payload(payload: dict) -> str:
    text = payload.get("text") or payload.get("transcription") or ""
    if not isinstance(text, str):
        text = str(text)
    return text.strip()


async def _transcribe_via_api(
    path: Path, filename: str, llm: LlmSettings, language: str
) -> AsrResult:
    api_base, api_key = resolve_asr_endpoint(llm)
    url = f"{api_base.rstrip('/')}/audio/transcriptions"
    model = resolve_asr_model(llm)
    headers = {"Authorization": f"Bearer {api_key}"}
    data = {
        "model": model,
        "language": language,
        "response_format": "json",
    }

    try:
        with path.open("rb") as handle:
            files = {"file": (filename, handle, _audio_mime(filename))}
            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
                response = await client.post(
                    url, headers=headers, data=data, files=files
                )
    except httpx.HTTPError as exc:
        raise AsrError(f"语音转写请求失败：{exc}") from exc

    if response.status_code >= 400:
        detail = response.text[:300]
        raise AsrError(f"语音转写接口返回 {response.status_code}：{detail}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise AsrError("语音转写接口返回了无法解析的内容。") from exc

    text = _parse_api_payload(payload if isinstance(payload, dict) else {})
    if not text:
        raise AsrError("语音转写没有返回文字内容。")
    return AsrResult(text=text, provider="api", model=model)


def _transcribe_local_sync(path: Path, language: str) -> AsrResult:
    from faster_whisper import WhisperModel

    model_name = (
        get_settings().asr_local_model.strip()
        or os.getenv("ASR_LOCAL_MODEL", DEFAULT_LOCAL_MODEL)
    )
    model = WhisperModel(model_name, device="auto", compute_type="int8")
    language_code = "zh" if language.lower().startswith("zh") else None
    segments, _info = model.transcribe(
        str(path),
        language=language_code,
        vad_filter=True,
        initial_prompt=(
            "以下是普通话简体中文的公务员考试课程讲解，涉及资料分析、"
            "数量关系、科学推理。常见术语：基期量、现期量、增长量、"
            "增长率、比重、平均数、截位直除、化同法、假设分配法、"
            "415份数法、排列组合、工程问题、行程问题、几何、"
            "科学推理、物理、化学、生物。"
            if language_code == "zh"
            else None
        ),
    )
    items = list(segments)
    text = "".join(segment.text for segment in items).strip()
    if not text:
        raise AsrError("本地语音转写没有识别到文字。")
    return AsrResult(
        text=text,
        provider="local",
        model=f"faster-whisper:{model_name}",
        segments=[
            (
                float(segment.start),
                float(segment.end),
                str(segment.text or "").strip(),
            )
            for segment in items
            if str(segment.text or "").strip()
        ],
    )


async def transcribe_file(
    path: Path,
    llm: LlmSettings,
    filename: str | None = None,
    language: str = "zh",
    deepseek: DeepSeekConfig | None = None,
) -> AsrResult:
    name = filename or path.name
    if deepseek and deepseek.ready and path.stat().st_size <= 8 * 1024 * 1024:
        try:
            text = await transcribe_audio(deepseek, path, name)
            return AsrResult(text=text, provider="deepseek", model="deepseek-asr")
        except DeepSeekError as exc:
            logger.warning(
                "DeepSeek ASR failed, falling back to configured ASR: %s", exc
            )
    if api_configured(llm):
        try:
            return await _transcribe_via_api(path, name, llm, language)
        except AsrError:
            if not local_available():
                raise
            logger.warning("ASR API failed, falling back to local Whisper", exc_info=True)
    if local_available():
        return await asyncio.wait_for(
            asyncio.to_thread(_transcribe_local_sync, path, language), timeout=1800
        )
    raise AsrUnavailable(
        "还没有可用的语音转写服务。请到设置页填写 LLM Base URL 和 API Key"
        "（支持 /audio/transcriptions 的供应商），或安装 faster-whisper 本地转写。"
    )


def _download_audio(url: str, temp_dir: str) -> Path:
    options = {
        "quiet": True,
        "no_warnings": True,
        "format": "bestaudio/best",
        "noplaylist": True,
        "socket_timeout": 30,
        "outtmpl": f"{temp_dir}/%(id)s.%(ext)s",
    }
    with yt_dlp.YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=True) or {}
        expected = Path(downloader.prepare_filename(info))
    if expected.exists():
        return expected
    candidates = sorted(Path(temp_dir).glob("*"), key=lambda item: item.stat().st_size)
    if not candidates:
        raise AsrError("视频音频下载失败。")
    return candidates[-1]


async def transcribe_video_url(
    url: str, llm: LlmSettings, language: str = "zh"
) -> AsrResult:
    if not asr_ready(llm):
        raise AsrUnavailable("语音转写未配置，视频只能索引简介。")

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            audio_path = await asyncio.wait_for(
                asyncio.to_thread(_download_audio, url, temp_dir), timeout=300
            )
        except Exception as exc:  # platform errors vary
            raise AsrError(f"视频音频下载失败：{exc}") from exc
        return await transcribe_file(
            audio_path, llm, filename=audio_path.name, language=language
        )
