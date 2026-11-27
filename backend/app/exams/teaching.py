"""交卷后由老师模型现场生成讲解和变式，而不是套预置模板。

预置模板的问题是千题一面：同一模块的不同题拿到同一段举一反三，讲解也
只是通用提示。这里改成让模型读题干、正确答案、学生的作答和对应技能的
完整步骤，针对这一道题讲清楚，并出贴合这道题考点的变式。

失败时一律回退到模板，不影响批改结果。
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field

import litellm

from app.config import get_settings
from app.schemas.settings import LlmSettings
from app.services.llm import normalize_model, role_model_config

logger = logging.getLogger(__name__)

GENERATE_MAX_TOKENS = 4000
GENERATE_TIMEOUT = 120
# 并发生成上限。再高容易触发供应商限流，重试反而更慢
TEACHING_CONCURRENCY = 4


@dataclass
class TeachingResult:
    """一道错题的讲解与变式。"""

    explanation: str = ""
    variants: list[dict] = field(default_factory=list)
    skill_usage: str = ""
    model: str = ""


def _option_lines(question) -> str:
    try:
        options = json.loads(question.options_json or "[]")
    except json.JSONDecodeError:
        options = []
    if not isinstance(options, list):
        return ""
    return "\n".join(
        f"{item.get('key')}. {item.get('text')}"
        for item in options
        if isinstance(item, dict) and item.get("key")
    )


def _answer_text(question) -> str:
    try:
        data = json.loads(question.answer_json or "{}")
    except json.JSONDecodeError:
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("value") or data.get("reference") or "").strip()


def _skill_block(skills: list[dict]) -> str:
    if not skills:
        return "（这道题没有匹配到技能，按你的教学经验讲）"
    parts = []
    for skill in skills[:2]:
        steps = "\n".join(f"  - {s}" for s in (skill.get("steps") or [])[:6])
        pitfalls = "、".join((skill.get("pitfalls") or [])[:4])
        signals = "、".join((skill.get("signals") or [])[:4])
        parts.append(
            f"技能：{skill.get('name')}\n"
            f"  适用信号：{signals or '未提供'}\n"
            f"  标准步骤：\n{steps or '  未提供'}\n"
            f"  常见陷阱：{pitfalls or '未提供'}"
        )
    return "\n\n".join(parts)


def _build_prompt(
    question,
    skills: list[dict],
    student_answer: str,
    correct_answer: str,
) -> str:
    options = _option_lines(question)
    return (
        "你是考公老师，正在给一个刚做错题的学生讲这道题。\n"
        "请针对这一道具体的题，不要泛泛而谈。\n\n"
        f"【题目】\n{question.stem}\n\n"
        f"【选项】\n{options or '（本题无选项）'}\n\n"
        f"【正确答案】{correct_answer or '未标注'}\n"
        f"【学生作答】{student_answer or '未作答'}\n\n"
        f"【这道题对应的技能】\n{_skill_block(skills)}\n\n"
        "只返回 JSON，不要 Markdown：\n"
        '{"explanation":"...","skill_usage":"...","variants":['
        '{"stem":"...","answer":"...","explanation":"..."}]}\n\n'
        "要求：\n"
        "1. explanation：讲清这道题，200 字以内。先点出学生错在哪一步，"
        "再走正确答案的思路。结合题干的具体条件，不要写空话。\n"
        "2. skill_usage：这道题怎么用上面那个技能，150 字以内。"
        "说清哪个信号触发了技能、技能哪一步对应题目哪一部分即可。\n"
        "3. variants：出 2 道变式题，每题 stem 和 explanation 各 60 字以内。"
        "必须换掉关键条件或换个问法，不能只改数字。\n"
        "4. 全部用中文，不要编造题干里没有的数据。\n"
        "请直接输出 JSON。"
    )


def _parse_result(text: str) -> TeachingResult:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        return TeachingResult()
    try:
        payload = json.loads(cleaned[start : end + 1], strict=False)
    except json.JSONDecodeError:
        return TeachingResult()

    variants: list[dict] = []
    raw_variants = payload.get("variants")
    if isinstance(raw_variants, list):
        for item in raw_variants[:3]:
            if not isinstance(item, dict):
                continue
            stem = str(item.get("stem") or "").strip()
            if len(stem) < 8:
                continue
            variants.append(
                {
                    "stem": stem[:500],
                    "answer": str(item.get("answer") or "").strip()[:200],
                    "explanation": str(item.get("explanation") or "").strip()[:800],
                }
            )
    return TeachingResult(
        explanation=str(payload.get("explanation") or "").strip()[:2000],
        skill_usage=str(payload.get("skill_usage") or "").strip()[:1500],
        variants=variants,
    )


async def generate_teaching(
    question,
    skills: list[dict],
    student_answer: str,
    llm: LlmSettings,
) -> TeachingResult | None:
    """给一道错题生成讲解与变式。失败返回 None，由调用方回退到模板。"""
    if get_settings().mock_llm:
        logger.warning("teaching: mock mode")
        return None
    endpoint = role_model_config(llm, "grader")
    if not endpoint.model:
        logger.warning("teaching: no grader model")
        return None

    kwargs: dict = {
        "model": normalize_model(endpoint.model),
        "messages": [
            {
                "role": "system",
                "content": "你是严谨的考公老师，只输出 JSON，不编造题目里没有的数据。",
            },
            {
                "role": "user",
                "content": _build_prompt(
                    question, skills, student_answer, _answer_text(question)
                ),
            },
        ],
        "temperature": 0.4,
        "max_tokens": max(endpoint.max_tokens or 0, GENERATE_MAX_TOKENS),
        "timeout": GENERATE_TIMEOUT,
        "response_format": {"type": "json_object"},
    }
    if endpoint.api_base:
        kwargs["api_base"] = endpoint.api_base
    if endpoint.api_key:
        kwargs["api_key"] = endpoint.api_key

    response = None
    # 批量批改时并发调用容易被限流，空响应多半是暂时性的，重试一次
    for attempt in range(3):
        try:
            response = await litellm.acompletion(**kwargs)
        except Exception:
            logger.warning("teaching generation failed", exc_info=True)
            response = None
        if response is not None and getattr(response, "choices", None):
            break
        if attempt < 2:
            # 退避：并发时被限流，等一会儿再来
            await asyncio.sleep(1.0 * (attempt + 1))

    choices = getattr(response, "choices", None) if response else None
    if not choices:
        logger.warning("teaching generation returned no choices")
        return None

    choice = choices[0]
    if getattr(choice, "finish_reason", "") == "length":
        logger.warning("teaching generation truncated")
        return None

    raw = str(choice.message.content or "")
    result = _parse_result(raw)
    if not result.explanation:
        # 输出被截断时 JSON 不完整，但开头的 explanation 往往已经出来了，
        # 用正则捞回来也比整条丢掉强。
        salvaged = _salvage(raw)
        if salvaged:
            logger.info("teaching: JSON truncated, salvaged explanation")
            result = TeachingResult(explanation=salvaged)
        else:
            logger.warning("teaching: parse failed, raw=%s", raw[:200])
            return None
    result.model = endpoint.model
    return result


def _salvage(raw: str) -> str:
    """从被截断的 JSON 里捞回 explanation 字段。"""
    import re

    match = re.search(
        r'"explanation"\s*:\s*"((?:[^"\\]|\\.)*)', raw
    )
    if not match:
        return ""
    text = match.group(1).encode().decode("unicode_escape", errors="ignore")
    return text.strip()[:2000]
