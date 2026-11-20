"""MVP video slide analysis: frames, OCR, slide grouping and summaries."""

import asyncio
import json
import logging
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

import httpx
import litellm
import yt_dlp
from PIL import Image

from app.config import DATA_DIR, get_settings
from app.rag.ocr import ocr_image
from app.rag.parsers import is_public_url
from app.rag.text import normalize_text
from app.rag.video import (
    TranscriptFetcher,
    _download_subtitles,
    _extract_info,
    _pick_subtitle,
)
from app.schemas.settings import LlmSettings
from app.services.llm import normalize_model, role_model_config

logger = logging.getLogger(__name__)

MAX_VIDEO_BYTES = 500 * 1024 * 1024
TARGET_FRAMES = 300
MIN_FRAME_INTERVAL = 2.0
MAX_OCR_TEXT = 1600
MAX_TRANSCRIPT = 1800
SUMMARY_BATCH = 6


class VideoSlidesError(RuntimeError):
    pass


@dataclass
class TimedLine:
    start: float
    end: float
    text: str


@dataclass
class FrameCandidate:
    index: int
    time: float
    path: Path
    hash: int
    text: str


@dataclass
class VideoSlide:
    index: int
    start: float
    end: float
    ocr_text: str
    frame_path: str = ""
    transcript: str = ""
    title: str = ""
    summary: str = ""
    points: list[str] = field(default_factory=list)


@dataclass
class VideoAnalysis:
    title: str
    duration: float
    slides: list[VideoSlide]
    transcript: str
    warning: str = ""


def format_time(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def parse_timed_subtitles(text: str) -> list[TimedLine]:
    lines: list[TimedLine] = []
    current: tuple[float, float] | None = None
    buffer: list[str] = []
    pattern = re.compile(
        r"(?:(\d{1,2}):)?(\d{1,2}):(\d{2})[.,](\d{1,3})\s*-->\s*"
        r"(?:(\d{1,2}):)?(\d{1,2}):(\d{2})[.,](\d{1,3})"
    )

    def stamp(hours: str | None, minutes: str, seconds: str, ms: str) -> float:
        return (
            int(hours or 0) * 3600
            + int(minutes) * 60
            + int(seconds)
            + int(ms.ljust(3, "0")[:3]) / 1000
        )

    def flush() -> None:
        if current is None:
            return
        value = normalize_text(" ".join(buffer)).strip()
        if value:
            lines.append(TimedLine(current[0], current[1], value))

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line == "WEBVTT" or line.startswith(("NOTE", "STYLE", "REGION")):
            continue
        match = pattern.search(line)
        if match:
            flush()
            buffer = []
            current = (
                stamp(match.group(1), match.group(2), match.group(3), match.group(4)),
                stamp(match.group(5), match.group(6), match.group(7), match.group(8)),
            )
            continue
        if current is None or line.isdigit():
            continue
        cleaned = re.sub(r"<[^>]+>", "", line).strip()
        if cleaned and (not buffer or buffer[-1] != cleaned):
            buffer.append(cleaned)
    flush()
    return lines


def _pseudo_timed_lines(text: str, duration: float) -> list[TimedLine]:
    sentences = [
        item.strip()
        for item in re.split(r"[。！？；\n]+", text)
        if len(item.strip()) >= 4
    ]
    if not sentences or duration <= 0:
        return []
    step = duration / len(sentences)
    return [
        TimedLine(i * step, (i + 1) * step, sentence)
        for i, sentence in enumerate(sentences)
    ]


def _dhash(path: Path, size: int = 8) -> int:
    try:
        with Image.open(path) as image:
            pixels = list(
                image.convert("L").resize((size + 1, size)).tobytes()
            )
    except Exception:  # noqa: BLE001 - damaged frame should not stop the job
        return 0
    value = 0
    for row in range(size):
        offset = row * (size + 1)
        for col in range(size):
            value = (value << 1) | (
                1 if pixels[offset + col] > pixels[offset + col + 1] else 0
            )
    return value


def _hamming(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def _text_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _same_slide(previous: VideoSlide, candidate: FrameCandidate) -> bool:
    if previous.frame_path:
        old_hash = _dhash(Path(previous.frame_path))
    else:
        old_hash = 0
    distance = _hamming(old_hash, candidate.hash) if old_hash else 8
    similarity = _text_similarity(previous.ocr_text, candidate.text)
    if similarity >= 0.72:
        return True
    if similarity >= 0.45 and distance <= 12:
        return True
    if previous.ocr_text and previous.ocr_text in candidate.text:
        return distance <= 16
    return False


def _pick_frame_interval(duration: float) -> float:
    if duration <= 0:
        return MIN_FRAME_INTERVAL
    return max(MIN_FRAME_INTERVAL, duration / TARGET_FRAMES)


def _download_video(url: str, temp_dir: Path) -> Path:
    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "format": "bv*[height<=480]/b[height<=480]/b",
        "outtmpl": f"{temp_dir}/video.%(ext)s",
        "socket_timeout": 30,
        "max_filesize": MAX_VIDEO_BYTES,
        "merge_output_format": "mp4",
    }
    with yt_dlp.YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=True) or {}
        expected = Path(downloader.prepare_filename(info))
    if expected.exists() and expected.stat().st_size > 0:
        return expected
    candidates = [
        item
        for item in Path(temp_dir).glob("video.*")
        if item.is_file() and item.suffix not in {".part", ".ytdl"}
    ]
    if not candidates:
        raise VideoSlidesError("视频下载失败。")
    return max(candidates, key=lambda item: item.stat().st_size)


def _extract_frames(
    video: Path, output_dir: Path, interval: float
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    pattern = output_dir / "frame-%05d.jpg"
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(video),
        "-vf",
        f"fps=1/{interval}",
        "-frames:v",
        str(TARGET_FRAMES + 20),
        "-q:v",
        "3",
        str(pattern),
    ]
    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            timeout=1800,
        )
    except FileNotFoundError as exc:
        raise VideoSlidesError("没有找到 ffmpeg，无法抽取视频画面。") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or b"").decode("utf-8", errors="replace")[:200]
        raise VideoSlidesError(f"ffmpeg 抽帧失败：{detail}") from exc
    except subprocess.TimeoutExpired as exc:
        raise VideoSlidesError("ffmpeg 抽帧超时。") from exc
    return sorted(output_dir.glob("frame-*.jpg"))


def _build_slides(
    frames: list[Path],
    interval: float,
    duration: float,
    material_id: str,
) -> list[VideoSlide]:
    slides: list[VideoSlide] = []
    frame_dir = DATA_DIR / "frames" / material_id
    frame_dir.mkdir(parents=True, exist_ok=True)
    effective_duration = duration or len(frames) * interval

    last_hash: int | None = None
    for index, path in enumerate(frames):
        frame_hash = _dhash(path)
        if slides and last_hash is not None and frame_hash == last_hash:
            slides[-1].end = min(
                effective_duration, index * interval + interval
            )
            continue
        text, _warning = ocr_image(path)
        text = text.strip()
        if len(text) < 6:
            continue
        candidate = FrameCandidate(
            index=index,
            time=index * interval,
            path=path,
            hash=frame_hash,
            text=text,
        )
        last_hash = frame_hash
        previous = slides[-1] if slides else None
        if previous is not None and _same_slide(previous, candidate):
            previous.end = min(effective_duration, candidate.time + interval)
            if len(candidate.text) > len(previous.ocr_text):
                previous.ocr_text = candidate.text
                previous.frame_path = str(candidate.path)
            continue
        slides.append(
            VideoSlide(
                index=len(slides),
                start=candidate.time,
                end=min(effective_duration, candidate.time + interval),
                ocr_text=candidate.text,
                frame_path=str(candidate.path),
            )
        )

    for position, slide in enumerate(slides):
        if position + 1 < len(slides):
            slide.end = max(slide.end, slides[position + 1].start)
        else:
            slide.end = effective_duration or slide.end
        source = Path(slide.frame_path)
        if source.exists():
            target = frame_dir / f"slide-{slide.index + 1:03d}.jpg"
            shutil.copyfile(source, target)
            slide.frame_path = f"frames/{material_id}/{target.name}"
        else:
            slide.frame_path = ""
        slide.index = position + 1
    return slides


def _load_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        value = json.loads(cleaned, strict=False)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end <= start:
            return {}
        try:
            value = json.loads(cleaned[start : end + 1], strict=False)
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}


def _fallback_summary(slide: VideoSlide) -> None:
    lines = [
        line.strip(" -·•\t")
        for line in slide.ocr_text.splitlines()
        if line.strip()
    ]
    slide.title = (lines[0] if lines else f"幻灯片 {slide.index}")[:60]
    source = slide.transcript or slide.ocr_text
    slide.summary = normalize_text(source)[:140]
    slide.points = [line[:100] for line in lines[1:6]]


def _build_prompt(video_title: str, slides: list[VideoSlide]) -> str:
    blocks = []
    for slide in slides:
        blocks.append(
            f"[{slide.index}] 时间：{format_time(slide.start)}–"
            f"{format_time(slide.end)}\n"
            f"幻灯片文字：\n{slide.ocr_text[:MAX_OCR_TEXT]}\n"
            f"讲解文字：\n{slide.transcript[:MAX_TRANSCRIPT] or '（无）'}"
        )
    return (
        f"你在整理视频课程《{video_title}》的逐页笔记。"
        "请为每一页输出标题、120 字以内摘要和 3–5 个要点。"
        "只返回 JSON，不要 Markdown，不要输出思考过程：\n"
        '{"slides":[{"index":1,"title":"...","summary":"...",'
        '"points":["..."]}]}\n'
        "要求：标题具体；摘要只基于给出的文字；要点可执行、可复习；"
        "不确定的内容不要编造。\n\n" + "\n\n".join(blocks)
    )


async def _summarize_batch(
    llm: LlmSettings,
    video_title: str,
    slides: list[VideoSlide],
) -> str:
    endpoint = role_model_config(llm, "knowledge")
    if not endpoint.model or get_settings().mock_llm:
        raise VideoSlidesError("summary model not configured")
    kwargs: dict = {
        "model": normalize_model(endpoint.model),
        "messages": [
            {
                "role": "system",
                "content": "你是严谨的考公课程笔记整理老师，只输出 JSON。",
            },
            {"role": "user", "content": _build_prompt(video_title, slides)},
        ],
        "temperature": min(endpoint.temperature, 0.3),
        "max_tokens": max(endpoint.max_tokens or 0, 8000),
        "timeout": 180,
        "response_format": {"type": "json_object"},
    }
    if endpoint.api_base:
        kwargs["api_base"] = endpoint.api_base
    if endpoint.api_key:
        kwargs["api_key"] = endpoint.api_key
    response = await litellm.acompletion(**kwargs)
    choice = response.choices[0]
    if getattr(choice, "finish_reason", "") == "length":
        raise VideoSlidesError("summary output truncated")
    payload = _load_json(str(choice.message.content or ""))
    items = payload.get("slides")
    if not isinstance(items, list):
        raise VideoSlidesError("summary JSON missing slides")
    known = {slide.index: slide for slide in slides}
    updated = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            index = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        slide = known.get(index)
        if slide is None:
            continue
        slide.title = str(item.get("title") or "").strip()[:80] or slide.title
        slide.summary = str(item.get("summary") or "").strip()[:300]
        points = item.get("points")
        if isinstance(points, list):
            slide.points = [
                str(point).strip()[:120]
                for point in points
                if str(point).strip()
            ][:6]
        updated += 1
    if not updated:
        raise VideoSlidesError("summary JSON had no matching slides")
    return endpoint.model


async def summarize_slides(
    llm: LlmSettings,
    video_title: str,
    slides: list[VideoSlide],
) -> tuple[str, str]:
    used = ""
    warnings: list[str] = []
    for start in range(0, len(slides), SUMMARY_BATCH):
        batch = slides[start : start + SUMMARY_BATCH]
        try:
            used = await _summarize_batch(llm, video_title, batch)
        except Exception as exc:  # noqa: BLE001 - fall back per slide
            logger.warning("video slide summary failed: %s", exc)
            warnings.append(str(exc)[:120])
    for slide in slides:
        if not slide.title or not slide.summary:
            _fallback_summary(slide)
    return used, ("；".join(warnings) if warnings else "")


def _timed_subtitle_url(info: dict) -> tuple[str, str]:
    return _pick_subtitle(info)[:2]


async def _fetch_timed_lines(
    url: str,
    info: dict,
    max_bytes: int,
) -> list[TimedLine]:
    subtitle_url, _language = _timed_subtitle_url(info)
    text = ""
    if subtitle_url and is_public_url(subtitle_url):
        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=httpx.Timeout(30.0)
            ) as client:
                response = await client.get(subtitle_url)
                response.raise_for_status()
                if len(response.content) <= max_bytes:
                    text = response.text
        except httpx.HTTPError:
            text = ""
    if not text:
        try:
            text = await asyncio.wait_for(
                asyncio.to_thread(_download_subtitles, url), timeout=120
            )
        except Exception:  # noqa: BLE001 - subtitle is best effort
            text = ""
    return parse_timed_subtitles(text)


def _align_transcript(
    slides: list[VideoSlide], lines: list[TimedLine]
) -> str:
    if not lines:
        return ""
    parts: list[str] = []
    for slide in slides:
        texts = [
            line.text
            for line in lines
            if line.start < slide.end and line.end > slide.start
        ]
        slide.transcript = " ".join(texts)[:4000]
        parts.extend(texts)
    return " ".join(parts)


def _slide_content(slide: VideoSlide) -> str:
    parts = [
        f"{slide.title}（{format_time(slide.start)}–{format_time(slide.end)}）",
    ]
    if slide.summary:
        parts.append(f"摘要：{slide.summary}")
    if slide.points:
        parts.append("要点：\n" + "\n".join(f"- {item}" for item in slide.points))
    if slide.transcript:
        parts.append(f"讲解：{slide.transcript[:MAX_TRANSCRIPT]}")
    parts.append(f"幻灯片文字：{slide.ocr_text[:MAX_OCR_TEXT]}")
    return "\n".join(parts)


def _analyze_sync(
    url: str,
    material_id: str,
    duration: float,
) -> list[VideoSlide]:
    interval = _pick_frame_interval(duration)

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        video = _download_video(url, root)
        frames = _extract_frames(video, root / "frames", interval)
        if not frames:
            raise VideoSlidesError("视频没有抽取到画面。")
        return _build_slides(frames, interval, duration, material_id)


async def _transcript_lines(
    url: str,
    info: dict,
    duration: float,
    max_bytes: int,
    transcriber: TranscriptFetcher | None,
) -> tuple[list[TimedLine], str]:
    lines = await _fetch_timed_lines(url, info, max_bytes)
    if lines:
        return lines, ""
    if transcriber is None:
        return [], ""
    try:
        result = await transcriber(url)
    except Exception as exc:  # noqa: BLE001 - subtitles remain the main source
        return [], f"语音转写失败：{str(exc)[:120]}"
    segments = getattr(result, "segments", None)
    if segments:
        return [
            TimedLine(float(start), float(end), str(text))
            for start, end, text in segments
            if str(text).strip()
        ], "视频没有字幕，已用带时间戳的语音转写对齐画面。"
    text = str(getattr(result, "text", "") or "").strip()
    if text:
        return (
            _pseudo_timed_lines(text, duration),
            "视频没有字幕，讲解按时间均分对齐到画面。",
        )
    return [], ""


async def analyze_video(
    url: str,
    material_id: str,
    llm: LlmSettings,
    max_bytes: int,
    transcriber: TranscriptFetcher | None = None,
) -> VideoAnalysis:
    try:
        info = await asyncio.to_thread(_extract_info, url)
    except Exception as exc:
        raise VideoSlidesError(f"视频解析失败：{exc}") from exc
    title = str(info.get("title") or "视频课程")[:255]
    duration = float(info.get("duration") or 0)

    slides = await asyncio.to_thread(
        _analyze_sync, url, material_id, duration
    )
    if not slides:
        raise VideoSlidesError("视频画面没有识别出幻灯片文字。")

    lines, warning = await _transcript_lines(
        url, info, duration, max_bytes, transcriber
    )
    transcript = _align_transcript(slides, lines)
    if not lines and not warning:
        warning = "视频没有带时间戳的字幕，逐页总结只使用幻灯片文字。"

    model, summary_warning = await summarize_slides(llm, title, slides)
    if summary_warning:
        warning = "；".join(item for item in (warning, summary_warning) if item)
    elif model:
        warning = "；".join(
            item for item in (warning, f"逐页总结：{model}") if item
        )
    return VideoAnalysis(
        title=title,
        duration=duration or (slides[-1].end if slides else 0),
        slides=slides,
        transcript=transcript,
        warning=warning,
    )


def slide_chunks(
    analysis: VideoAnalysis,
) -> list[dict]:
    return [
        {
            "content": _slide_content(slide),
            "heading": slide.title or f"幻灯片 {slide.index}",
            "heading_path": f"{analysis.title} > {slide.title or '幻灯片'}",
            "page": slide.index,
            "time_start": slide.start,
            "time_end": slide.end,
            "frame_path": slide.frame_path,
        }
        for slide in analysis.slides
    ]


def clear_frames(material_id: str) -> None:
    folder = DATA_DIR / "frames" / material_id
    if folder.exists():
        shutil.rmtree(folder, ignore_errors=True)


__all__ = [
    "TimedLine",
    "VideoAnalysis",
    "VideoSlide",
    "VideoSlidesError",
    "analyze_video",
    "clear_frames",
    "format_time",
    "parse_timed_subtitles",
    "slide_chunks",
    "summarize_slides",
]
