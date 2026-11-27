"""校验知识单元的可核对出处。

模型很容易编一个页码或原文短句。这里在落库前核对：页码必须落在这次输入
的范围内，短句必须真能在那一页的原文里找到。对不上就降级为待审，
而不是当成可靠知识留下来。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 引用短句至少这么长才有核对意义。中文 6 个字已足够定位
MIN_QUOTE_CHARS = 6


def _normalize(text: str) -> str:
    """去掉空白和标点，只留实义字符，避免排版差异导致误判。"""
    return re.sub(r"[\s　]+|[，。、；：？！,.;:?!“”\"'（）()【】\[\]]", "", text or "")


@dataclass
class EvidenceCheck:
    ok: bool
    reason: str = ""


def check_evidence(
    evidence: object,
    page_texts: dict[int, str],
    allowed_pages: set[int] | None = None,
) -> EvidenceCheck:
    """核对一条知识的出处。

    Args:
        evidence: 模型返回的 evidence，可以是 dict 或 list[dict]
        page_texts: 本次输入里每页的原文
        allowed_pages: 本次输入覆盖的页码；为空表示不限制
    """
    items = evidence if isinstance(evidence, list) else [evidence]
    items = [item for item in items if isinstance(item, dict)]
    if not items:
        return EvidenceCheck(False, "缺少出处")

    for item in items:
        try:
            page = int(item.get("page") or 0)
        except (TypeError, ValueError):
            page = 0
        quote = str(item.get("quote") or "").strip()

        # page=0 表示模型自认是推导内容，允许，但要能看出来
        if page == 0:
            return EvidenceCheck(True, "")

        if allowed_pages and page not in allowed_pages:
            return EvidenceCheck(False, f"引用页码 {page} 不在本次输入范围")

        source = page_texts.get(page, "")
        if not source:
            return EvidenceCheck(False, f"第 {page} 页没有原文可核对")

        if len(_normalize(quote)) < MIN_QUOTE_CHARS:
            return EvidenceCheck(False, "引用原文过短")

        needle = _normalize(quote)
        if needle in _normalize(source):
            continue

        # 页码可能标错了。原文确实在资料里，只是不在标的那一页，
        # 这种情况值得保留，让审核的人顺手改页码即可。
        elsewhere = [
            num
            for num, text in page_texts.items()
            if num != page and needle in _normalize(text)
        ]
        if elsewhere:
            return EvidenceCheck(
                True, f"引用在第 {elsewhere[0]} 页，页码标注有误"
            )

        return EvidenceCheck(False, f"第 {page} 页找不到这句原文")

    return EvidenceCheck(True, "")
