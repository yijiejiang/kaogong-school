"""资料题的准入校验：不合格的题不能进可组卷池。

抽取是机器做的，模型会漏答案、给出不在选项里的字母、或者干脆没认出题干。
这些题一旦被标成 approved 就会进试卷，而判分又拿不到有效答案，
最后污染成绩和掌握度。所以入库前必须逐题校验，不合格的退回待审。
"""

from __future__ import annotations

import json
import re

OPTION_KEYS = ("A", "B", "C", "D", "E", "F")


def _load_options(raw: str) -> list[str]:
    try:
        items = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(items, list):
        return []
    keys = []
    for item in items:
        if isinstance(item, dict) and item.get("key"):
            keys.append(str(item["key"]).strip().upper()[:1])
    return keys


def _load_answer(raw: str) -> str:
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("value") or "").strip().upper()


def _normalize_stem(text: str) -> str:
    """去掉题号后判断题干是否真的存在。"""
    return re.sub(r"^[\s\d.．、]+", "", text or "").strip()


def check_question(
    *,
    qtype: str,
    stem: str,
    options_json: str,
    answer_json: str,
    rubric_json: str = "",
) -> tuple[bool, str]:
    """返回 (是否可自动通过, 不通过的原因)。

    只有确定能作答、能判分的题才返回 True。宁可多审几道，
    也不让一道判不了的题混进试卷。
    """
    if not _normalize_stem(stem):
        return False, "题干缺失"

    keys = _load_options(options_json)
    answer = _load_answer(answer_json)
    qtype = (qtype or "single").lower()

    if qtype == "single":
        if len(keys) < 2:
            return False, "选项不足"
        if not answer:
            return False, "答案缺失"
        if len(answer) != 1 or answer not in keys:
            return False, f"答案 {answer} 不在选项中"
        return True, ""

    if qtype == "multiple":
        if len(keys) < 2:
            return False, "选项不足"
        if not answer:
            return False, "答案缺失"
        picked = {ch for ch in answer if ch.isalpha()}
        if not picked:
            return False, "答案缺失"
        unknown = picked - set(keys)
        if unknown:
            return False, f"答案 {''.join(sorted(unknown))} 不在选项中"
        return True, ""

    if qtype == "short":
        # 主观题靠评分细则判分，没有细则就没法给分
        try:
            rubric = json.loads(rubric_json or "[]")
        except json.JSONDecodeError:
            rubric = []
        if not isinstance(rubric, list) or not rubric:
            return False, "缺少评分细则"
        return True, ""

    return False, f"未知题型 {qtype}"


def is_usable_answer(answer_json: str, options_json: str) -> bool:
    """判分前再确认一次：没有有效答案的题不该参与计分。"""
    answer = _load_answer(answer_json)
    if not answer:
        return False
    keys = _load_options(options_json)
    if not keys:
        return False
    return all(ch in keys for ch in answer if ch.isalpha())
