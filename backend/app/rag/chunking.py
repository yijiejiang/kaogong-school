"""Structure-aware chunking for Chinese study materials."""

import re
from dataclasses import dataclass

from app.rag.text import normalize_text

_MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
_CHAPTER_RE = re.compile(r"^第[一二三四五六七八九十百零两\d]+[编章部分节]\s*(.*)$")
_SECTION_RE = re.compile(r"^([一二三四五六七八九十]+)[、．.]\s*(.+)$")
_DECIMAL_RE = re.compile(r"^(\d+(?:\.\d+){1,3})[、．.]?\s+(\S.*)$")
_PAREN_RE = re.compile(r"^[（(]([一二三四五六七八九十\d]+)[)）]\s*(.+)$")
_CJK_RE = re.compile(r"[一-鿿]")


@dataclass
class TextChunk:
    content: str
    heading: str = ""
    heading_path: str = ""
    page: int | None = None


def _heading(line: str) -> tuple[int, str] | None:
    match = _MARKDOWN_HEADING_RE.match(line)
    if match:
        return len(match.group(1)), match.group(2).strip()

    match = _CHAPTER_RE.match(line)
    if match and _CJK_RE.search(match.group(1)):
        title = match.group(1).strip()
        return 1, title or line.strip()

    match = _SECTION_RE.match(line)
    if match and _CJK_RE.search(match.group(2)):
        return 2, match.group(2).strip(" ：:.-—")

    match = _DECIMAL_RE.match(line)
    if match and _CJK_RE.search(match.group(2)):
        level = 2 + min(match.group(1).count(".") + 1, 2)
        return level, match.group(2).strip(" ：:.-—")

    match = _PAREN_RE.match(line)
    if match and _CJK_RE.search(match.group(2)):
        return 3, match.group(2).strip(" ：:.-—")

    return None


def _segments(text: str) -> list[tuple[str, str, str]]:
    segments: list[tuple[str, str, str]] = []
    stack: list[tuple[int, str]] = []
    heading = ""
    heading_path = ""
    buffer: list[str] = []

    for raw in text.splitlines():
        line = raw.strip()
        hit = _heading(line)
        if hit is None:
            buffer.append(raw)
            continue
        if buffer:
            segments.append(("\n".join(buffer), heading, heading_path))
            buffer = []
        level, title = hit
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        heading = title
        heading_path = " > ".join(item[1] for item in stack)

    if buffer:
        segments.append(("\n".join(buffer), heading, heading_path))
    return segments


def chunk_text(
    text: str,
    max_chars: int = 800,
    overlap: int = 100,
) -> list[TextChunk]:
    text = normalize_text(text)
    if not text:
        return []

    chunks: list[TextChunk] = []
    for segment, heading, heading_path in _segments(text):
        blocks = [
            block.strip()
            for block in re.split(r"\n\s*\n", segment)
            if block.strip()
        ]
        chunks.extend(
            _chunk_blocks(blocks, heading, heading_path, max_chars, overlap)
        )
    return chunks


def _chunk_blocks(
    blocks: list[str],
    heading: str,
    heading_path: str,
    max_chars: int,
    overlap: int,
) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    buffer = ""

    for block in blocks:
        if len(block) > max_chars:
            if buffer:
                chunks.append(
                    TextChunk(buffer.strip(), heading, heading_path)
                )
                buffer = ""
            for piece in _split_long(block, max_chars, overlap):
                chunks.append(TextChunk(piece, heading, heading_path))
            continue

        candidate = f"{buffer}\n\n{block}".strip() if buffer else block
        if len(candidate) <= max_chars:
            buffer = candidate
            continue

        if buffer:
            chunks.append(TextChunk(buffer.strip(), heading, heading_path))
        tail = _tail(buffer, overlap) if buffer else ""
        buffer = f"{tail}\n\n{block}".strip() if tail else block
        if len(buffer) > max_chars:
            pieces = _split_long(buffer, max_chars, overlap)
            for piece in pieces[:-1]:
                chunks.append(TextChunk(piece, heading, heading_path))
            buffer = pieces[-1] if pieces else ""

    if buffer.strip():
        chunks.append(TextChunk(buffer.strip(), heading, heading_path))

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
