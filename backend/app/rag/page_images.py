"""把文字层稀薄的页面渲染成图片，供 OCR 或视觉模型补读。

扫描件和图表页的正文在文字层里几乎为空。整本按扫描件处理代价太大，
逐页判断更划算：只把真正读不出内容的页拿去识别，其余页用现成文字。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pymupdf

logger = logging.getLogger(__name__)

# 一页的有效字数低于这个值，就认为这页靠不住
SPARSE_PAGE_CHARS = 50
# 渲染分辨率。150 dpi 足够看清字体，又不至于让图片过大
RENDER_DPI = 150
# 单次最多渲染多少页，防止一本大部头把所有页都渲染一遍
MAX_RENDER_PAGES = 200


@dataclass
class PageImage:
    page: int
    path: Path
    width: int
    height: int


def meaningful_chars(text: str) -> int:
    """只数有意义的字符，排除页码、水印这类零散噪声。"""
    import re

    cleaned = re.sub(r"[\s\d\W_]+", "", text or "", flags=re.UNICODE)
    return len(cleaned)


def is_sparse_page(text: str) -> bool:
    """这一页是不是读不出多少内容（扫描页或纯图表页）。"""
    return meaningful_chars(text) < SPARSE_PAGE_CHARS


def find_sparse_pages(pages: list[tuple[int, str]]) -> list[int]:
    """返回需要补读的页码（1 起）。"""
    return [page for page, text in pages if is_sparse_page(text)][:MAX_RENDER_PAGES]


def render_pages(
    pdf_path: Path,
    page_numbers: list[int],
    out_dir: Path,
) -> list[PageImage]:
    """把指定页渲染成 PNG，返回每页的文件路径。

    页码是 1 起的自然页序，和 OCR 返回的页码保持一致。
    """
    if not page_numbers:
        return []

    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[PageImage] = []
    zoom = RENDER_DPI / 72.0
    matrix = pymupdf.Matrix(zoom, zoom)

    document = pymupdf.open(pdf_path)
    try:
        for page_number in page_numbers:
            index = page_number - 1
            if index < 0 or index >= document.page_count:
                continue
            try:
                pixmap = document[index].get_pixmap(matrix=matrix, alpha=False)
            except Exception:
                logger.warning("render page %s failed", page_number, exc_info=True)
                continue
            target = out_dir / f"p{page_number:04d}.png"
            pixmap.save(target)
            results.append(
                PageImage(
                    page=page_number,
                    path=target,
                    width=pixmap.width,
                    height=pixmap.height,
                )
            )
    finally:
        document.close()
    return results
