"""Structure-aware chunking for Chinese study materials."""

import re
from dataclasses import dataclass

from app.rag.text import normalize_text

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")


@dataclass
class TextChunk:
    content: str
    heading: str = ""
    page: int | None = None


def chunk_text(
    text: str,
    max_chars: int = 800,
    overlap: int = 100,
) -> list[TextChunk]:
    text = normalize_text(text)
    if not text:
        return []

    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    chunks: list[TextChunk] = []
    buffer = ""
    heading = ""

    for block in blocks:
        match = _HEADING_RE.match(block)
        if match:
            heading = match.group(2).strip()

        if len(block) > max_chars:
            if buffer:
                chunks.append(TextChunk(buffer.strip(), heading))
                buffer = ""
            for piece in _split_long(block, max_chars, overlap):
                chunks.append(TextChunk(piece, heading))
            continue

        candidate = f"{buffer}\n\n{block}".strip() if buffer else block
        if len(candidate) <= max_chars:
            buffer = candidate
            continue

        if buffer:
            chunks.append(TextChunk(buffer.strip(), heading))
        tail = _tail(buffer, overlap) if buffer else ""
        buffer = f"{tail}\n\n{block}".strip() if tail else block
        if len(buffer) > max_chars:
            pieces = _split_long(buffer, max_chars, overlap)
            for piece in pieces[:-1]:
                chunks.append(TextChunk(piece, heading))
            buffer = pieces[-1] if pieces else ""

    if buffer.strip():
        chunks.append(TextChunk(buffer.strip(), heading))

    return chunks


def _split_long(text: str, max_chars: int, overlap: int) -> list[str]:
    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            window = text[start:end]
            cut = max(
                window.rfind("。"),
                window.rfind("！"),
                window.rfind("？"),
                window.rfind("\n"),
            )
            if cut > max_chars // 2:
                end = start + cut + 1
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return pieces


def _tail(text: str, limit: int) -> str:
    if not text:
        return ""
    tail = text[-limit:]
    for punct in ("。", "！", "？", "\n"):
        index = tail.find(punct)
        if index != -1 and index < len(tail) - 20:
            return tail[index + 1 :].strip()
    return tail.strip()
