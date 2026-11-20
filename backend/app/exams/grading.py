"""Objective and rubric-based grading, 举一反三, mastery and error book."""

import asyncio
import json
import logging
import re
import uuid
from typing import Any

from litellm import acompletion
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import (
    Answer,
    Attempt,
    ErrorBook,
    Exam,
    ExamQuestion,
    Mastery,
    Question,
    SkillMastery,
    utcnow,
)
from app.schemas.settings import LlmSettings
from app.services.llm import normalize_model, role_model_config
from app.services.settings_service import load_llm_settings
from app.services.skill_matching import load_skill_index, match_skills

logger = logging.getLogger(__name__)

GENERIC_VARIANTS = [
    {
        "stem": "变式1：把题干中的数字换成另一组，先判断题型再列式。",
        "answer": "先写公式，再代入计算。",
        "explanation": "先判断是增长率、比重还是平均数，再选公式。",
    },
    {
        "stem": "变式2：把问题从求现期改成求基期，注意公式变形。",
        "answer": "基期=现期÷(1+增长率)。",
        "explanation": "增长率题和基期题经常互换。",
    },
    {
        "stem": "变式3：选项差距变小，练习保留更多有效数字。",
        "answer": "先看选项差距，再决定截几位。",
        "explanation": "差距小的时候不要过度截位。",
    },
]

VARIANT_TEMPLATES: dict[str, list[dict]] = {
    "xingce-ziliao-zengzhang": [
        {
            "stem": "基期 1200，现期 1500，增长率是多少？",
            "answer": "25%",
            "explanation": "(1500-1200)÷1200=25%。",
        },
        {
            "stem": "现期 1800，增长率 20%，基期是多少？",
            "answer": "1500",
            "explanation": "1800÷1.2=1500。",
        },
        {
            "stem": "增长率 15%，增长量 300，基期是多少？",
            "answer": "2000",
            "explanation": "300÷15%=2000。",
        },
    ],
    "xingce-ziliao-bizhong": [
        {
            "stem": "部分 320，整体 800，比重是多少？",
            "answer": "40%",
            "explanation": "320÷800=40%。",
        },
        {
            "stem": "整体 1200，比重 25%，部分是多少？",
            "answer": "300",
            "explanation": "1200×25%=300。",
        },
        {
            "stem": "部分增速 12%，整体增速 8%，比重如何变化？",
            "answer": "上升",
            "explanation": "部分增速大于整体增速，比重上升。",
        },
    ],
    "xingce-ziliao-susuan": [
        {
            "stem": "估算 4832÷1276，最接近哪个数？",
            "answer": "3.8",
            "explanation": "分母截前三位，分子同比截位后相除。",
        },
        {
            "stem": "把 1276 看成 1280 估算，误差方向是什么？",
            "answer": "结果偏小",
            "explanation": "分母变大，商变小。",
        },
        {
            "stem": "选项差距很小时，截几位更稳妥？",
            "answer": "保留 3 到 4 位有效数字",
            "explanation": "差距小不要过度截位。",
        },
    ],
    "xingce-ziliao-pingjun": [
        {
            "stem": "总量 1200，份数 150，平均数是多少？",
            "answer": "8",
            "explanation": "1200÷150=8。",
        },
        {
            "stem": "平均数 12，份数 80，总量是多少？",
            "answer": "960",
            "explanation": "12×80=960。",
        },
        {
            "stem": "总量增长 20%，份数不变，平均数怎么变？",
            "answer": "增长 20%",
            "explanation": "总量除以相同份数，平均数同比例变化。",
        },
    ],
    "xingce-ziliao-beishu": [
        {
            "stem": "A=800，B=200，A 是 B 的几倍？",
            "answer": "4 倍",
            "explanation": "800÷200=4。",
        },
        {
            "stem": "A 是 B 的 3 倍，B=150，A 是多少？",
            "answer": "450",
            "explanation": "150×3=450。",
        },
        {
            "stem": "A 比 B 多 3 倍，A 是 B 的几倍？",
            "answer": "4 倍",
            "explanation": "多 3 倍 = 是 4 倍。",
        },
    ],
}


def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {}


def _response_text(response: Any) -> str:
    if response is None:
        return ""
    if isinstance(response, list):
        return " ".join(str(item) for item in response)
    return str(response)


def _objective_correct(question: Question, response: Any, answer_value: Any) -> bool:
    if question.type == "multiple":
        if not isinstance(response, list):
            return False
        return sorted(str(item) for item in response) == sorted(
            str(item) for item in (answer_value or [])
        )
    return str(response or "") == str(answer_value or "")


def _variants_for(question: Question) -> list[dict]:
    return VARIANT_TEMPLATES.get(question.knowledge_point_id, GENERIC_VARIANTS)


def _grade_short_keywords(
    question: Question, text: str, max_score: float
) -> tuple[float, list[dict], list[str], str]:
    try:
        rubric = json.loads(question.rubric_json or "[]")
    except json.JSONDecodeError:
        rubric = []

    normalized = text.replace(" ", "").lower()
    total = 0.0
    hit_points: list[dict] = []
    missed_points: list[str] = []
    for point in rubric:
        keywords = [str(keyword) for keyword in point.get("keywords", [])]
        if any(
            keyword.replace(" ", "").lower() in normalized for keyword in keywords
        ):
            total += float(point.get("score", 1))
            hit_points.append(
                {"point": str(point.get("point", "")), "evidence": ""}
            )
        else:
            missed_points.append(str(point.get("point", "")))

    total = min(total, max_score)
    comment = (
        f"本地演示评分：命中 {len(hit_points)} 个得分点。"
        if hit_points
        else "本地演示评分：没有命中评分细则。"
    )
    return total, hit_points, missed_points, comment


async def _grade_short_with_llm(
    question: Question,
    text: str,
    max_score: float,
    llm: LlmSettings,
) -> tuple[float, list[dict], list[str], str] | None:
    if get_settings().mock_llm:
        return None
    endpoint = role_model_config(llm, "grader")
    if not endpoint.model:
        return None

    try:
        answer_data = json.loads(question.answer_json or "{}")
        rubric = json.loads(question.rubric_json or "[]")
    except json.JSONDecodeError:
        return None

    prompt = f"""题目：{question.stem}
参考答案：{answer_data.get('reference', '')}
评分细则：{json.dumps(rubric, ensure_ascii=False)}
学生答案：{text}

请按评分细则给分，只返回 JSON：
{{"score": number, "hit_points": [{{"point": "...", "evidence": "..."}}], "missed_points": ["..."], "comment": "..."}}"""

    try:
        kwargs: dict = {
            "model": normalize_model(endpoint.model),
            "api_base": endpoint.api_base or None,
            "api_key": endpoint.api_key or None,
            "messages": [
                {
                    "role": "system",
                    "content": "你是严谨的考公阅卷老师，只输出 JSON。",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        if endpoint.max_tokens > 0:
            kwargs["max_tokens"] = endpoint.max_tokens
        if 0 < endpoint.top_p <= 1:
            kwargs["top_p"] = endpoint.top_p
        completion = await asyncio.wait_for(
            acompletion(**kwargs),
            timeout=45,
        )
        content = completion.choices[0].message.content or ""
        data = _extract_json(content)
        if not data:
            return None
        score = min(max_score, max(0.0, float(data.get("score", 0))))
        hit_points = data.get("hit_points") or []
        missed_points = data.get("missed_points") or []
        comment = str(data.get("comment") or "")
        return score, hit_points, missed_points, comment
    except Exception:
        logger.exception("LLM short-answer grading failed; using rubric keywords")
        return None


async def _grade_short(
    question: Question,
    response: Any,
    max_score: float,
    llm: LlmSettings,
) -> tuple[float, list[dict], list[str], str]:
    text = _response_text(response).strip()
    if not text:
        try:
            rubric = json.loads(question.rubric_json or "[]")
        except json.JSONDecodeError:
            rubric = []
        return (
            0.0,
            [],
            [str(point.get("point", "")) for point in rubric],
            "未作答。",
        )

    llm_result = await _grade_short_with_llm(question, text, max_score, llm)
    if llm_result is not None:
        return llm_result
    return _grade_short_keywords(question, text, max_score)


async def grade_attempt(
    db: AsyncSession,
    attempt: Attempt,
    exam: Exam,
    rows: list[tuple[ExamQuestion, Question]],
    answer_rows: list[Answer],
) -> dict:
    llm = await load_llm_settings(db)
    answer_by_question = {row.question_id: row for row in answer_rows}
    skill_index = await load_skill_index(db)
    mastery_before: dict[str, dict] = {}
    mastery_rows: dict[str, Mastery] = {}
    mastery_accum: dict[str, dict] = {}
    skill_accum: dict[str, dict] = {}
    skill_before: dict[str, dict] = {}

    feedbacks: list[dict] = []
    score_total = 0.0
    correct_count = 0
    wrong_count = 0

    for link, question in rows:
        answer_row = answer_by_question.get(question.id)
        if answer_row is None:
            answer_row = Answer(
                id=uuid.uuid4().hex,
                attempt_id=attempt.id,
                question_id=question.id,
                response_json="null",
                max_score=link.score,
            )
            db.add(answer_row)

        try:
            response = json.loads(answer_row.response_json or "null")
        except json.JSONDecodeError:
            response = None
        try:
            answer_data = json.loads(question.answer_json or "{}")
        except json.JSONDecodeError:
            answer_data = {}
        try:
            options = json.loads(question.options_json or "[]")
        except json.JSONDecodeError:
            options = []
        try:
            rubric = json.loads(question.rubric_json or "[]")
        except json.JSONDecodeError:
            rubric = []

        hit_points: list[dict] = []
        missed_points: list[str] = []
        comment = ""
        if question.type == "short":
            score, hit_points, missed_points, comment = await _grade_short(
                question, response, link.score, llm
            )
            is_correct = score >= link.score * 0.6
            correct_answer = answer_data.get("reference", "")
        else:
            correct_answer = answer_data.get("value")
            is_correct = _objective_correct(question, response, correct_answer)
            score = link.score if is_correct else 0.0
            comment = "回答正确。" if is_correct else "回答错误。"

        score_total += score
        if is_correct:
            correct_count += 1
        else:
            wrong_count += 1

        matched_skills = match_skills(
            f"{question.stem}\n{question.explanation}",
            question.knowledge_point_id,
            skill_index,
        )
        if question.skill_id:
            forced = next(
                (
                    item
                    for item in skill_index.get(
                        question.knowledge_point_id, []
                    )
                    if item["id"] == question.skill_id
                ),
                None,
            )
            if forced is not None:
                matched_skills = [forced] + [
                    item
                    for item in matched_skills
                    if item["id"] != forced["id"]
                ]
        primary_skill = matched_skills[0] if matched_skills else None

        feedback = {
            "question_id": question.id,
            "order_index": link.order_index,
            "type": question.type,
            "stem": question.stem,
            "options": options,
            "user_answer": response,
            "correct_answer": correct_answer,
            "is_correct": is_correct,
            "score": round(score, 1),
            "max_score": round(link.score, 1),
            "explanation": question.explanation,
            "knowledge_point_id": question.knowledge_point_id,
            "knowledge_point_name": question.knowledge_point_name,
            "rubric": rubric,
            "hit_points": hit_points,
            "missed_points": missed_points,
            "comment": comment,
            "variants": [] if is_correct else _variants_for(question),
            "skills": matched_skills,
        }
        feedbacks.append(feedback)

        kp_id = question.knowledge_point_id or question.module or "unclassified"
        kp_name = question.knowledge_point_name or question.module or "未分类"
        bucket = mastery_accum.setdefault(
            kp_id, {"name": kp_name, "scores": [], "correct": 0}
        )
        bucket["scores"].append(score / link.score if link.score else 0.0)
        bucket["correct"] += 1 if is_correct else 0

        if primary_skill is not None:
            skill_id = primary_skill["id"]
            skill_bucket = skill_accum.setdefault(
                skill_id,
                {"name": primary_skill["name"], "scores": [], "correct": 0},
            )
            skill_bucket["scores"].append(
                score / link.score if link.score else 0.0
            )
            skill_bucket["correct"] += 1 if is_correct else 0

        if not is_correct:
            existing_error = (
                await db.execute(
                    select(ErrorBook).where(
                        ErrorBook.user_id == attempt.user_id,
                        ErrorBook.question_id == question.id,
                    )
                )
            ).scalar_one_or_none()
            if existing_error is not None:
                existing_error.times_wrong += 1
                existing_error.resolved = False
                existing_error.attempt_id = attempt.id
                existing_error.knowledge_point_id = kp_id
                existing_error.knowledge_point_name = kp_name
            else:
                db.add(
                    ErrorBook(
                        id=uuid.uuid4().hex,
                        user_id=attempt.user_id,
                        question_id=question.id,
                        attempt_id=attempt.id,
                        knowledge_point_id=kp_id,
                        knowledge_point_name=kp_name,
                    )
                )

        answer_row.response_json = json.dumps(response, ensure_ascii=False)
        answer_row.score = score
        answer_row.max_score = link.score
        answer_row.is_correct = is_correct
        answer_row.feedback_json = json.dumps(feedback, ensure_ascii=False)

    for kp_id, bucket in mastery_accum.items():
        row_id = f"{attempt.user_id}:{kp_id}"
        mastery = await db.get(Mastery, row_id)
        if mastery is None:
            mastery = Mastery(
                id=row_id,
                user_id=attempt.user_id,
                knowledge_point_id=kp_id,
                knowledge_point_name=bucket["name"],
                score=50.0,
                attempts=0,
                correct=0,
            )
            db.add(mastery)

        old_score = mastery.score if mastery.score is not None else 50.0
        mastery_before[kp_id] = {"name": bucket["name"], "score": old_score}
        scores = bucket["scores"]
        average = sum(scores) / len(scores) if scores else 0.0
        mastery.score = round(
            max(0.0, min(100.0, old_score * 0.7 + average * 100 * 0.3)), 1
        )
        mastery.attempts = (mastery.attempts or 0) + len(scores)
        mastery.correct = (mastery.correct or 0) + bucket["correct"]
        mastery.last_practiced = utcnow()
        mastery.knowledge_point_name = bucket["name"]
        mastery_rows[kp_id] = mastery

    skill_rows: dict[str, SkillMastery] = {}
    for skill_id, bucket in skill_accum.items():
        row_id = f"{attempt.user_id}:{skill_id}"
        mastery = await db.get(SkillMastery, row_id)
        if mastery is None:
            mastery = SkillMastery(
                id=row_id,
                user_id=attempt.user_id,
                skill_id=skill_id,
                skill_name=bucket["name"],
                score=50.0,
                attempts=0,
                correct=0,
            )
            db.add(mastery)
        old_score = mastery.score if mastery.score is not None else 50.0
        skill_before[skill_id] = {
            "skill_id": skill_id,
            "skill_name": bucket["name"],
            "before": round(old_score, 1),
        }
        scores = bucket["scores"]
        average = sum(scores) / len(scores) if scores else 0.0
        mastery.score = round(
            max(0.0, min(100.0, old_score * 0.7 + average * 100 * 0.3)), 1
        )
        mastery.attempts = (mastery.attempts or 0) + len(scores)
        mastery.correct = (mastery.correct or 0) + bucket["correct"]
        mastery.last_practiced = utcnow()
        mastery.skill_name = bucket["name"]
        skill_rows[skill_id] = mastery

    skill_changes = [
        {
            **before,
            "after": skill_rows[skill_id].score,
            "attempts": skill_rows[skill_id].attempts,
        }
        for skill_id, before in skill_before.items()
    ]

    total_score = sum(link.score for link, _ in rows)
    mastery_changes = [
        {
            "knowledge_point_id": kp_id,
            "knowledge_point_name": before["name"],
            "before": round(before["score"], 1),
            "after": mastery_rows[kp_id].score,
            "attempts": mastery_rows[kp_id].attempts,
        }
        for kp_id, before in mastery_before.items()
    ]

    await db.commit()
    return {
        "attempt_id": attempt.id,
        "exam_id": exam.id,
        "exam_title": exam.title,
        "score": round(score_total, 1),
        "total_score": round(total_score, 1),
        "percentage": (
            round(score_total / total_score * 100, 1) if total_score else 0.0
        ),
        "submitted_at": utcnow().isoformat(),
        "questions": feedbacks,
        "mastery_changes": mastery_changes,
        "skill_changes": skill_changes,
        "error_book_added": wrong_count,
        "summary": (
            f"得分 {score_total:.1f}/{total_score:.1f}，"
            f"正确 {correct_count}/{len(rows)} 题。"
        ),
    }
