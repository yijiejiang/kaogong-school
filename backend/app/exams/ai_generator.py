"""AI-authored exam questions through the configured OpenAI-compatible model."""

import json
import re
import uuid
from dataclasses import dataclass, field

import litellm

from app.config import get_settings
from app.schemas.settings import LlmSettings
from app.services.llm import normalize_model, resolve_role_model


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


def _extract_questions(text: str) -> list[dict]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise AiGenerationError("AI 没有返回可解析的题目 JSON。") from None
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise AiGenerationError("AI 返回的题目 JSON 无法解析。") from exc

    if isinstance(payload, dict):
        payload = payload.get("questions") or payload.get("items") or []
    if not isinstance(payload, list):
        raise AiGenerationError("AI 返回的题目格式不正确。")
    return [item for item in payload if isinstance(item, dict)]


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

    model_name = resolve_role_model(llm, "examiner") or llm.default_model.strip()
    if not model_name:
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
        "model": normalize_model(model_name),
        "messages": messages,
        "temperature": 0.5,
        "max_tokens": max(1200, count * 500),
        "timeout": 120,
    }
    if llm.api_base.strip():
        kwargs["api_base"] = llm.api_base.strip()
    if llm.api_key.strip():
        kwargs["api_key"] = llm.api_key.strip()

    try:
        response = await litellm.acompletion(**kwargs)
    except Exception as exc:
        raise AiGenerationError(f"AI 命题请求失败：{str(exc)[:200]}") from exc

    try:
        text = response.choices[0].message.content or ""
    except (AttributeError, IndexError, KeyError) as exc:
        raise AiGenerationError("AI 命题返回为空。") from exc

    raw_questions = _extract_questions(str(text))
    questions: list[dict] = []
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
        if len(questions) >= count:
            break

    if not questions:
        raise AiGenerationError("AI 生成的内容没有通过题目校验。")

    usage = getattr(response, "usage", None)
    return AiGenerationResult(
        questions=questions,
        prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
        completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
        model=model_name,
    )
