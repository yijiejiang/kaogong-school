"""Video URL ingestion via yt-dlp subtitles and optional ASR fallback."""

import asyncio
import re
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from urllib.parse import urlparse

import httpx
import yt_dlp

from app.rag.parsers import FetchError, ParsedDocument, is_public_url
from app.rag.text import normalize_text

VIDEO_HOSTS = ("bilibili.com", "b23.tv", "youtube.com", "youtu.be", "vimeo.com")
LANGUAGE_ORDER = ("zh-Hans", "zh-CN", "zh", "zh-Hant", "en", "en-US")

TranscriptFetcher = Callable[[str], Awaitable[object]]


def is_video_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == item or host.endswith("." + item) for item in VIDEO_HOSTS)


def _extract_info(url: str) -> dict:
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": 30,
    }
    with yt_dlp.YoutubeDL(options) as downloader:
        return downloader.extract_info(url, download=False) or {}


def _pick_subtitle(info: dict) -> tuple[str, str, bool]:
    sources = [
        (info.get("subtitles") or {}, False),
        (info.get("automatic_captions") or {}, True),
    ]
    for source, automatic in sources:
        for language in LANGUAGE_ORDER:
            for entry in source.get(language) or []:
                if entry.get("ext") in {"vtt", "srt"} and entry.get("url"):
                    return str(entry["url"]), language, automatic
    return "", "", False


def clean_subtitles(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if (
            not line
            or line == "WEBVTT"
            or line.startswith("NOTE")
            or "-->" in line
            or line.isdigit()
        ):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        if line and (not lines or lines[-1] != line):
            lines.append(line)
    return normalize_text("\n".join(lines))


def _download_subtitles(url: str) -> str:
    with tempfile.TemporaryDirectory() as temp_dir:
        options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": list(LANGUAGE_ORDER),
            "subtitlesformat": "vtt/best",
            "noplaylist": True,
            "socket_timeout": 30,
            "outtmpl": f"{temp_dir}/%(id)s.%(ext)s",
        }
        with yt_dlp.YoutubeDL(options) as downloader:
            downloader.download([url])
        for path in sorted(Path(temp_dir).glob("*.vtt")):
            return path.read_text(encoding="utf-8", errors="replace")
    return ""


async def fetch_video(
    url: str,
    max_bytes: int,
    transcriber: TranscriptFetcher | None = None,
) -> ParsedDocument:
    try:
        info = await asyncio.wait_for(
            asyncio.to_thread(_extract_info, url), timeout=120
        )
    except Exception as exc:
        raise FetchError(f"视频解析失败：{exc}") from exc

    title = str(info.get("title") or urlparse(url).hostname or "视频资料")
    description = normalize_text(str(info.get("description") or ""))
    subtitle_url, _language, _automatic = _pick_subtitle(info)
    subtitle_text = ""
    warning = ""

    if subtitle_url and is_public_url(subtitle_url):
        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=httpx.Timeout(30.0)
            ) as client:
                response = await client.get(subtitle_url)
                response.raise_for_status()
                if len(response.content) <= max_bytes:
                    subtitle_text = clean_subtitles(response.text)
        except httpx.HTTPError:
            subtitle_text = ""
    elif not subtitle_text:
        try:
            downloaded = await asyncio.wait_for(
                asyncio.to_thread(_download_subtitles, url), timeout=120
            )
            subtitle_text = clean_subtitles(downloaded)
        except Exception:  # noqa: BLE001 - description-only fallback
            subtitle_text = ""

    if not subtitle_text and transcriber is not None:
        try:
            result = await transcriber(url)
            text = str(getattr(result, "text", "") or "").strip()
            if text:
                subtitle_text = text
                model = getattr(result, "model", "ASR")
                warning = f"视频没有字幕，已用语音转写（{model}）生成文字稿。"
        except Exception as exc:  # noqa: BLE001 - fall back to description
            warning = f"语音转写失败：{str(exc)[:160]}"

    text = "\n\n".join(part for part in (description, subtitle_text) if part)
    if not subtitle_text and not warning:
        warning = "视频没有可用字幕，只索引了简介；可在设置页配置语音转写。"
    if not text.strip():
        raise FetchError("视频没有字幕、语音转写或简介可索引。")

    return ParsedDocument(
        title=title[:255],
        text=text,
        pages=[(1, text)],
        kind="video",
        mime_type="text/vtt",
        warning=warning,
    )
