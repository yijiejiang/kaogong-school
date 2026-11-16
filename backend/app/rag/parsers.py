"""File and web parsing with a small SSRF guard."""

import ipaddress
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
from app.rag.text import normalize_text

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


def sanitize_filename(filename: str) -> str:
    name = Path(filename).name
    name = "".join(char for char in name if char.isprintable())
    name = name.replace("/", "_").replace("\\", "_").replace(":", "_").strip()
    return (name or "document")[:180]


def parse_file(path: Path, filename: str, mime_type: str = "") -> ParsedDocument:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return _parse_pdf(path, filename, mime_type)
    if suffix == ".docx":
        return _parse_docx(path, filename, mime_type)
    if suffix in {".txt", ".md", ".markdown"}:
        return _parse_text(path, filename, mime_type)
    if suffix in IMAGE_SUFFIXES:
        return _parse_image(path, filename, mime_type)
    raise UnsupportedFileType(
        "当前支持 PDF、DOCX、TXT、Markdown、PNG/JPG 图片。"
    )


def _parse_image(path: Path, filename: str, mime_type: str) -> ParsedDocument:
    text, warning = ocr_image(path)
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


def _parse_pdf(path: Path, filename: str, mime_type: str) -> ParsedDocument:
    document = pymupdf.open(path)
    pages: list[tuple[int, str]] = []
    empty_pages = 0
    try:
        for index, page in enumerate(document):
            text = normalize_text(page.get_text("text"))
            if not text:
                empty_pages += 1
            pages.append((index + 1, text))
        metadata = document.metadata or {}
    finally:
        document.close()

    text = "\n\n".join(page_text for _, page_text in pages if page_text)
    title = str(metadata.get("title") or "").strip() or Path(filename).stem
    warning = ""
    if pages and empty_pages / len(pages) > 0.5:
        warning = "多数页面没有可提取文字，可能是扫描版 PDF；P1 暂未接入 OCR。"
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


async def fetch_url(url: str, max_bytes: int) -> ParsedDocument:
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
            )

    raise FetchError("重定向次数过多。")
