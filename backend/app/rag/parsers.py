"""File and web parsing with a small SSRF guard."""

import ipaddress
import re
import socket
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import docx
import httpx
import pymupdf
from bs4 import BeautifulSoup

from app.rag.ocr import ocr_image
from app.rag.page_images import find_sparse_pages
from app.rag.text import normalize_text
from app.services.deepseek_tools import (
    DeepSeekConfig,
    DeepSeekError,
    fetch_page,
    ocr_file_sync,
)

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


class ParseError(RuntimeError):
    pass


class UnsupportedFileType(ParseError):
    pass


class UnsafeUrl(ParseError):
    pass


class FetchError(ParseError):
    pass


@dataclass
class ParsedDocument:
    title: str
    text: str
    pages: list[tuple[int, str]]
    kind: str = "file"
    mime_type: str = ""
    warning: str = ""
    ocr_pages: int = 0


# Collects paid OCR pages while parsing; ingestion drains this after the job.
_ocr_budget: list[int] = []


def record_ocr_pages(count: int) -> None:
    if count > 0:
        _ocr_budget.append(int(count))


def drain_ocr_pages() -> int:
    total = sum(_ocr_budget)
    _ocr_budget.clear()
    return total


def sanitize_filename(filename: str) -> str:
    name = Path(filename).name
    name = "".join(char for char in name if char.isprintable())
    name = name.replace("/", "_").replace("\\", "_").replace(":", "_").strip()
    return (name or "document")[:180]


def parse_file(
    path: Path,
    filename: str,
    mime_type: str = "",
    deepseek: DeepSeekConfig | None = None,
) -> ParsedDocument:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return _parse_pdf(path, filename, mime_type, deepseek)
    if suffix == ".docx":
        return _parse_docx(path, filename, mime_type)
    if suffix in {".txt", ".md", ".markdown"}:
        return _parse_text(path, filename, mime_type)
    if suffix in IMAGE_SUFFIXES:
        return _parse_image(path, filename, mime_type, deepseek)
    raise UnsupportedFileType(
        "当前支持 PDF、DOCX、TXT、Markdown、PNG/JPG 图片。"
    )


def _parse_image(
    path: Path,
    filename: str,
    mime_type: str,
    deepseek: DeepSeekConfig | None = None,
) -> ParsedDocument:
    text, warning = ocr_image(path)
    if not text.strip() and deepseek and deepseek.ready:
        try:
            pages = ocr_file_sync(deepseek, path, filename)
            text = "\n\n".join(page.text for page in pages)
            warning = "DeepSeek OCR"
            record_ocr_pages(len(pages))
        except DeepSeekError as exc:
            warning = f"{warning}；DeepSeek OCR 失败：{exc}"
    if not text.strip():
        raise ParseError(warning or "图片没有识别出文字。")
    return ParsedDocument(
        title=Path(filename).stem,
        text=text,
        pages=[(1, text)],
        kind="image",
        mime_type=mime_type or "image/png",
        warning=warning,
    )


def _strip_page_noise(pages: list[tuple[int, str]]) -> list[tuple[int, str]]:
    if not pages:
        return pages
    threshold = max(2, int(len(pages) * 0.6))
    counts: dict[str, int] = {}
    for _, page_text in pages:
        seen = {
            line.strip()
            for line in page_text.splitlines()
            if line.strip()
        }
        for line in seen:
            counts[line] = counts.get(line, 0) + 1

    cleaned: list[tuple[int, str]] = []
    for number, page_text in pages:
        kept: list[str] = []
        for line in page_text.splitlines():
            value = line.strip()
            if not value:
                kept.append("")
                continue
            if _is_page_noise(value, counts.get(value, 0), threshold):
                continue
            kept.append(_strip_dot_leader(value))
        cleaned.append((number, "\n".join(kept)))
    return cleaned


_PAGE_MARK_RE = re.compile(r"^[-—\s]*第?\s*\d{1,3}\s*页?[-—\s]*$")


def _is_page_noise(line: str, occurrences: int, threshold: int) -> bool:
    if _PAGE_MARK_RE.match(line):
        return True
    if len(line) <= 80 and occurrences >= threshold:
        return True
    stripped = re.sub(r"[\s.·…\-_=*#]+", "", line)
    return len(line) > 4 and len(stripped) <= max(1, len(line) // 8)


def _strip_dot_leader(line: str) -> str:
    value = re.sub(r"[.·…]{3,}\s*\d{0,3}\s*$", "", line).rstrip(" .·…")
    return value or line


SCANNED_PAGE_CHARS = 50      # 平均每页少于这么多有效字符，就当作扫描件
OCR_BATCH_PAGES = 20          # 每批送给 DeepSeek OCR 的页数
OCR_MAX_PAGES = 1000          # 官方单次上限


def _meaningful_chars(text: str) -> int:
    """只统计有意义的字符，排除页码、水印这类零散噪声。"""
    cleaned = re.sub(r"[\s\d\W_]+", "", text, flags=re.UNICODE)
    return len(cleaned)


def _looks_scanned(pages: list[tuple[int, str]]) -> bool:
    if not pages:
        return False
    total = sum(_meaningful_chars(text) for _, text in pages)
    return total / len(pages) < SCANNED_PAGE_CHARS


def _ocr_in_batches(
    config: DeepSeekConfig,
    path: Path,
    filename: str,
    total_pages: int,
) -> tuple[list[tuple[int, str]], list[str], int]:
    """按页分批调用 OCR，单批失败不影响其它批次。

    返回 (页文本, 警告, 截断页数)。页码保持与原始 PDF 对齐。
    """
    collected: dict[int, str] = {}
    warnings: list[str] = []
    truncated = 0
    limit = min(total_pages, OCR_MAX_PAGES)
    if total_pages > OCR_MAX_PAGES:
        warnings.append(f"PDF 超过 {OCR_MAX_PAGES} 页，只识别前 {OCR_MAX_PAGES} 页。")

    document = pymupdf.open(path)
    try:
        for start in range(0, limit, OCR_BATCH_PAGES):
            end = min(start + OCR_BATCH_PAGES, limit)
            temp_path: Path | None = None
            try:
                batch = pymupdf.open()
                batch.insert_pdf(document, from_page=start, to_page=end - 1)
                with tempfile.NamedTemporaryFile(
                    suffix=".pdf", delete=False
                ) as handle:
                    batch.save(handle.name)
                    temp_path = Path(handle.name)
                batch.close()

                pages = ocr_file_sync(
                    config,
                    temp_path,
                    filename,
                    start_page=start,
                )
                for page in pages:
                    collected[page.index] = page.text
                    if page.truncated:
                        truncated += 1
            except DeepSeekError as exc:
                warnings.append(f"第 {start + 1}-{end} 页 OCR 失败：{exc}")
            except Exception as exc:  # noqa: BLE001 - 单批失败不影响整体
                warnings.append(f"第 {start + 1}-{end} 页处理异常：{exc}")
            finally:
                if temp_path is not None:
                    temp_path.unlink(missing_ok=True)
    finally:
        document.close()

    ordered = sorted(collected.items())
    return ordered, warnings, truncated


def _parse_pdf(
    path: Path,
    filename: str,
    mime_type: str,
    deepseek: DeepSeekConfig | None = None,
) -> ParsedDocument:
    document = pymupdf.open(path)
    pages: list[tuple[int, str]] = []
    try:
        for index, page in enumerate(document):
            text = normalize_text(page.get_text("text"))
            pages.append((index + 1, text))
        metadata = document.metadata or {}
    finally:
        document.close()

    warning = ""
    warnings: list[str] = []
    # 逐页判断：一份资料里通常只有几页是扫描页或纯图表页，
    # 整本送 OCR 既慢又费钱。
    sparse_pages = find_sparse_pages(pages)
    if sparse_pages:
        warning = f"有 {len(sparse_pages)} 页文字层稀薄（疑似扫描页或图表页）。"
        if deepseek and deepseek.ready:
            ocr_pages, ocr_warnings, truncated = _ocr_in_batches(
                deepseek, path, filename, len(pages)
            )
            if ocr_pages:
                # OCR 结果按页覆盖，未识别到的页保留原有文字层
                existing = dict(pages)
                existing.update(dict(ocr_pages))
                pages = sorted(existing.items())
                warning = f"已用 DeepSeek OCR 识别 {len(ocr_pages)} 页。"
                record_ocr_pages(len(ocr_pages))
            if truncated:
                warnings.append(f"{truncated} 页输出被截断，内容可能不完整。")
            warnings.extend(ocr_warnings)
        else:
            warnings.append("未配置 DeepSeek Key，稀疏页只能保留占位引用。")

    pages = _strip_page_noise(pages)
    text = "\n\n".join(page_text for _, page_text in pages if page_text)
    title = str(metadata.get("title") or "").strip() or Path(filename).stem
    if not text.strip():
        warnings.append("PDF 没有可提取文字。")
    if warnings:
        warning = " ".join([item for item in [warning, *warnings] if item])
    return ParsedDocument(
        title=title,
        text=text,
        pages=pages,
        kind="file",
        mime_type=mime_type or "application/pdf",
        warning=warning,
    )


def _parse_docx(path: Path, filename: str, mime_type: str) -> ParsedDocument:
    document = docx.Document(str(path))
    paragraphs = [
        normalize_text(paragraph.text)
        for paragraph in document.paragraphs
        if paragraph.text.strip()
    ]
    text = "\n\n".join(paragraphs)
    title = str(document.core_properties.title or "").strip() or Path(filename).stem
    return ParsedDocument(
        title=title,
        text=text,
        pages=[(1, text)],
        kind="file",
        mime_type=mime_type
        or "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


def _parse_text(path: Path, filename: str, mime_type: str) -> ParsedDocument:
    raw = path.read_bytes()
    text = ""
    for encoding in ("utf-8", "gb18030", "utf-16"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if not text:
        text = raw.decode("utf-8", errors="replace")

    text = normalize_text(text)
    title = Path(filename).stem
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break
    return ParsedDocument(
        title=title,
        text=text,
        pages=[(1, text)],
        kind="file",
        mime_type=mime_type or "text/plain",
    )


def is_public_url(url: str) -> bool:
    if not url or len(url) > 2048:
        return False
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    if parsed.username or parsed.password:
        return False

    host = parsed.hostname.lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        return False

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False

    for info in infos:
        address = info[4][0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return False
        if not ip.is_global or ip.is_multicast:
            return False
    return True


async def fetch_url(
    url: str,
    max_bytes: int,
    deepseek: DeepSeekConfig | None = None,
) -> ParsedDocument:
    deepseek_warning = ""
    if (
        deepseek
        and deepseek.ready
        and not urlparse(url).path.lower().endswith(".pdf")
        and is_public_url(url)
    ):
        try:
            page = await fetch_page(deepseek, url)
            content = page["content"].strip()
            if content:
                if len(content.encode("utf-8")) > max_bytes:
                    raise FetchError("网页内容过大，已停止抓取。")
                return ParsedDocument(
                    title=page["title"] or (urlparse(url).hostname or "网页资料"),
                    text=content,
                    pages=[(1, content)],
                    kind="url",
                    mime_type="text/markdown",
                    warning="DeepSeek 抓取",
                )
        except (DeepSeekError, FetchError) as exc:
            deepseek_warning = f"DeepSeek 抓取失败，已回退本地解析：{exc}"

    current = url
    headers = {"User-Agent": "KaogongSchool/0.1 (local personal study tool)"}

    async with httpx.AsyncClient(
        follow_redirects=False,
        timeout=httpx.Timeout(20.0),
        headers=headers,
    ) as client:
        for _ in range(3):
            if not is_public_url(current):
                raise UnsafeUrl("只允许抓取公网 http/https 地址。")

            try:
                response = await client.get(current)
            except httpx.HTTPError as exc:
                raise FetchError(f"抓取失败：{exc}") from exc

            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise FetchError("重定向缺少 Location。")
                current = urljoin(current, location)
                continue

            if response.status_code >= 400:
                raise FetchError(f"网页返回 HTTP {response.status_code}。")

            content_type = response.headers.get("content-type", "").lower()
            payload_parts: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    raise FetchError("网页内容过大，已停止抓取。")
                payload_parts.append(chunk)
            payload = b"".join(payload_parts)

            if "application/pdf" in content_type:
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    tmp.write(payload)
                    tmp_path = Path(tmp.name)
                try:
                    return parse_file(
                        tmp_path,
                        f"{urlparse(current).hostname or 'web'}.pdf",
                        content_type,
                        deepseek,
                    )
                finally:
                    tmp_path.unlink(missing_ok=True)

            charset = response.encoding or "utf-8"
            try:
                html = payload.decode(charset, errors="replace")
            except LookupError:
                html = payload.decode("utf-8", errors="replace")

            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(
                ["script", "style", "noscript", "iframe", "svg", "nav", "footer", "header", "form"]
            ):
                tag.decompose()

            title = ""
            if soup.title and soup.title.string:
                title = soup.title.string.strip()
            if not title:
                h1 = soup.find("h1")
                title = h1.get_text(" ", strip=True) if h1 else ""

            main = soup.find("article") or soup.find("main") or soup.body or soup
            text = normalize_text(main.get_text("\n"))
            return ParsedDocument(
                title=title or (urlparse(current).hostname or "网页资料"),
                text=text,
                pages=[(1, text)],
                kind="url",
                mime_type=content_type,
                warning=deepseek_warning,
            )

    raise FetchError("重定向次数过多。")
