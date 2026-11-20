"""AI-authored exam questions through the configured OpenAI-compatible model."""

import json
import logging
import re
import uuid
from dataclasses import dataclass, field

import litellm

from app.config import get_settings
from app.schemas.settings import LlmSettings
from app.services.llm import normalize_model, role_model_config

logger = logging.getLogger(__name__)


class AiGenerationError(RuntimeError):
    """AI question generation failed; callers fall back to the seed bank."""


@dataclass
class AiGenerationResult:
    questions: list[dict] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""


DIFFICULTY_HINTS = {
    "easy": "简单（基础概念、直接套公式）",
    "medium": "中等（需要两步推理或辨析）",
    "hard": "困难（多知识点综合、干扰项较强）",
    "mixed": "混合（简单、中等、困难各占一部分）",
}


def _difficulty_value(label: str, index: int) -> int:
    if label == "easy":
        return 2
    if label == "hard":
        return 4
    if label == "mixed":
        return [2, 3, 3, 4][index % 4]
    return 3


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    if text.endswith("```"):
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _json_candidates(text: str) -> list[str]:
    """Extract balanced JSON objects/arrays, tolerating prose around them."""
    candidates: list[str] = []
    for index, char in enumerate(text):
        if char not in "[{":
            continue
        depth = 0
        in_string = False
        escaped = False
        for position in range(index, len(text)):
            current = text[position]
            if in_string:
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == '"':
                    in_string = False
                continue
            if current == '"':
                in_string = True
            elif current in "[{":
                depth += 1
            elif current in "]}":
                depth -= 1
                if depth == 0:
                    candidate = text[index : position + 1]
                    if candidate not in candidates:
                        candidates.append(candidate)
                    break
    return candidates


def _remove_trailing_commas(text: str) -> str:
    return re.sub(r",\s*([}\]])", r"\1", text)


def _looks_like_question(item: object) -> bool:
    return (
        isinstance(item, dict)
        and bool(item.get("stem") or item.get("question"))
        and ("options" in item or "answer" in item)
    )


def _questions_from_payload(payload: object) -> list[dict] | None:
    if isinstance(payload, dict):
        payload = payload.get("questions") or payload.get("items")
    if not isinstance(payload, list):
        return None
    items = [item for item in payload if isinstance(item, dict)]
    if not any(_looks_like_question(item) for item in items):
        return None
    return items


def _extract_questions(text: str) -> list[dict]:
    cleaned = _strip_fences(text)
    candidates = [cleaned, *_json_candidates(cleaned)]
    for candidate in candidates:
        for attempt in (candidate, _remove_trailing_commas(candidate)):
            try:
                payload = json.loads(attempt, strict=False)
            except json.JSONDecodeError:
                continue
            questions = _questions_from_payload(payload)
            if questions is not None:
                return questions

    # The outer object may be malformed while individual question objects are
    # still valid; salvage those instead of failing the whole response.
    salvaged: list[dict] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate.startswith("{"):
            continue
        for attempt in (candidate, _remove_trailing_commas(candidate)):
            try:
                payload = json.loads(attempt, strict=False)
            except json.JSONDecodeError:
                continue
            if not _looks_like_question(payload):
                continue
            stem = str(payload.get("stem") or payload.get("question") or "")
            if stem in seen:
                continue
            seen.add(stem)
            salvaged.append(payload)
            break
    if salvaged:
        return salvaged

    logger.warning(
        "failed to parse AI question JSON: %s", cleaned[:4000]
    )
    raise AiGenerationError("AI 返回的题目 JSON 无法解析。") from None


def _normalize_options(raw_options: object) -> list[dict]:
    if not isinstance(raw_options, list):
        return []
    options: list[dict] = []
    for index, item in enumerate(raw_options[:4]):
        key = "ABCD"[index]
        if isinstance(item, dict):
            text = str(item.get("text") or item.get("content") or "").strip()
            key = str(item.get("key") or key).strip().upper()[:1] or key
        else:
            text = str(item).strip()
        if text:
            options.append({"key": key, "text": text})
    return options


def _normalize_question(
    raw: dict,
    *,
    subject: str,
    module: str,
    kp_options: list[dict],
    difficulty: str,
    index: int,
) -> dict | None:
    stem = str(raw.get("stem") or raw.get("question") or "").strip()
    options = _normalize_options(raw.get("options"))
    if not stem or len(options) != 4:
        return None
    keys = {item["key"] for item in options}
    if keys != set("ABCD"):
        options = [
            {"key": "ABCD"[i], "text": item["text"]}
            for i, item in enumerate(options)
        ]
        keys = set("ABCD")

    answer = str(raw.get("answer") or raw.get("correct") or "").strip().upper()
    if answer not in keys:
        matched = next(
            (item["key"] for item in options if item["text"] == answer), ""
        )
        if not matched:
            return None
        answer = matched

    kp_id = str(raw.get("knowledge_point_id") or "").strip()
    kp_name = str(raw.get("knowledge_point_name") or "").strip()
    allowed = {item["id"]: item["name"] for item in kp_options}
    if kp_id not in allowed:
        matched = next(
            (item["id"] for item in kp_options if item["name"] == kp_name), ""
        )
        kp_id = matched or (kp_options[0]["id"] if kp_options else "")
    if not kp_id:
        return None
    kp_name = allowed.get(kp_id, kp_name or "综合")

    return {
        "id": f"ai-{uuid.uuid4().hex[:16]}",
        "type": "single",
        "subject": subject,
        "module": module,
        "knowledge_point_id": kp_id,
        "knowledge_point_name": kp_name,
        "stem": stem[:2000],
        "options_json": json.dumps(options, ensure_ascii=False),
        "answer_json": json.dumps({"value": answer}, ensure_ascii=False),
        "rubric_json": "[]",
        "explanation": str(raw.get("explanation") or "").strip()[:2000],
        "difficulty": _difficulty_value(difficulty, index),
        "source": "ai",
        "quality_status": "approved",
    }


def _build_prompt(
    subject: str,
    module: str,
    count: int,
    difficulty: str,
    kp_options: list[dict],
) -> str:
    kp_lines = "\n".join(
        f"- {item['id']}：{item['name']}" for item in kp_options
    )
    return (
        f"你是公务员考试命题专家。请为「{subject}·{module}」命制 {count} 道单项选择题。\n"
        f"难度：{DIFFICULTY_HINTS.get(difficulty, DIFFICULTY_HINTS['medium'])}。\n"
        f"知识点只能从下面选择，并原样填写 id：\n{kp_lines}\n\n"
        "要求：\n"
        "1. 题干完整、无歧义，四个选项 A/B/C/D 中只有一个正确答案。\n"
        "2. answer 必须是 A/B/C/D 之一。\n"
        "3. explanation 用一两句话说明解题思路。\n"
        "4. 不要照抄常见原题，数字和情境可以自拟。\n"
        '5. 只输出 JSON 对象：{"questions": [{"stem": "...", '
        '"options": [{"key": "A", "text": "..."}, ...], "answer": "A", '
        '"explanation": "...", "knowledge_point_id": "...", '
        '"knowledge_point_name": "..."}]}\n'
        "不要输出 Markdown 代码块或任何解释性文字。"
    )


async def generate_ai_questions(
    llm: LlmSettings,
    *,
    subject: str,
    module: str,
    count: int,
    difficulty: str,
    kp_options: list[dict],
) -> AiGenerationResult:
    if count <= 0:
        return AiGenerationResult()
    if get_settings().mock_llm:
        raise AiGenerationError(
            "本地演示模式不会调用 AI 命题。配置真实 LLM 后可使用 AI 原创题。"
        )

    endpoint = role_model_config(llm, "examiner")
    if not endpoint.model:
        raise AiGenerationError("还没有配置出卷老师的模型，无法生成 AI 原创题。")

    messages = [
        {
            "role": "system",
            "content": (
                "你是一名严谨的公务员考试命题专家，只输出符合要求的 JSON。"
            ),
        },
        {
            "role": "user",
            "content": _build_prompt(
                subject, module, count, difficulty, kp_options
            ),
        },
    ]
    kwargs: dict = {
        "model": normalize_model(endpoint.model),
        "messages": messages,
        "temperature": endpoint.temperature,
        "max_tokens": endpoint.max_tokens or max(2000, count * 800),
        "timeout": 120,
    }
    if endpoint.api_base:
        kwargs["api_base"] = endpoint.api_base
    if endpoint.api_key:
        kwargs["api_key"] = endpoint.api_key
    if 0 < endpoint.top_p <= 1:
        kwargs["top_p"] = endpoint.top_p

    prompt_tokens = 0
    completion_tokens = 0
    questions: list[dict] = []
    last_error = ""
    for attempt in range(3):
        attempt_kwargs = dict(kwargs)
        if attempt == 0:
            attempt_kwargs["response_format"] = {"type": "json_object"}
        else:
            attempt_kwargs["temperature"] = min(endpoint.temperature, 0.2)
            attempt_kwargs["max_tokens"] = max(
                int(attempt_kwargs.get("max_tokens") or 0), 3000
            )
            retry_messages = [dict(item) for item in messages]
            retry_messages[1]["content"] = (
                messages[1]["content"]
                + "\n\n上一次输出没有通过 JSON 校验。请严格只输出一个合法 JSON "
                "对象；字符串中不要出现未转义的换行或引号。"
            )
            attempt_kwargs["messages"] = retry_messages

        try:
            response = await litellm.acompletion(**attempt_kwargs)
        except Exception as exc:  # noqa: BLE001 - provider errors vary
            last_error = f"AI 命题请求失败：{str(exc)[:200]}"
            continue

        usage = getattr(response, "usage", None)
        prompt_tokens += int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens += int(
            getattr(usage, "completion_tokens", 0) or 0
        )

        try:
            text = str(response.choices[0].message.content or "")
        except (AttributeError, IndexError, KeyError):
            last_error = "AI 命题返回为空。"
            continue
        if not text.strip():
            last_error = "AI 命题返回为空。"
            continue

        try:
            raw_questions = _extract_questions(text)
        except AiGenerationError as exc:
            last_error = str(exc)
            continue

        for index, raw in enumerate(raw_questions):
            normalized = _normalize_question(
                raw,
                subject=subject,
                module=module,
                kp_options=kp_options,
                difficulty=difficulty,
                index=index,
            )
            if normalized is not None:
                questions.append(normalized)
            else:
                logger.warning(
                    "AI question rejected: %s",
                    json.dumps(raw, ensure_ascii=False)[:1500],
                )
            if len(questions) >= count:
                break
        if questions:
            break
        last_error = "AI 生成的内容没有通过题目校验。"

    if not questions:
        raise AiGenerationError(f"{last_error}（已尝试 3 次）")

    return AiGenerationResult(
        questions=questions,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        model=endpoint.model,
    )
