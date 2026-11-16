"""Text normalization and lightweight Chinese tokenization."""

import re

import jieba

for _word in (
    "资料分析",
    "截位直除",
    "两期比重",
    "隔年增长率",
    "混合增长率",
    "逻辑填空",
    "片段阅读",
    "图形推理",
    "定义判断",
    "类比推理",
    "逻辑判断",
    "归纳概括",
    "综合分析",
    "提出对策",
    "贯彻执行",
    "文章写作",
):
    jieba.add_word(_word)


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    tokens: list[str] = []
    for token in jieba.cut_for_search(lowered):
        token = token.strip()
        if len(token) >= 2 and not token.isdigit():
            tokens.append(token)
    for segment in re.findall(r"[一-鿿]+", lowered):
        for index in range(len(segment) - 1):
            tokens.append(segment[index : index + 2])
    return tokens


def keyword_score(query: str, text: str) -> float:
    query_tokens = {token for token in tokenize(query) if len(token) >= 2}
    if not query_tokens:
        return 0.0
    hits = sum(1 for token in query_tokens if token in text)
    return hits / len(query_tokens)


def truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"
