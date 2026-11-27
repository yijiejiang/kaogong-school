"""Exam generation, attempt lifecycle, and report retrieval."""

import asyncio
import json
import logging
import random
import uuid
from datetime import UTC
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Answer,
    Attempt,
    Exam,
    ExamQuestion,
    KnowledgePoint,
    Question,
    utcnow,
)
from app.exams.ai_generator import AiGenerationError, generate_ai_questions
from app.exams.grading import grade_attempt
from app.schemas.settings import LlmSettings
from app.services.llm import role_model_config
from app.services.skill_matching import load_skill_index, match_skills
from app.services.usage import record_usage

logger = logging.getLogger(__name__)

# 后台批改任务，防止被 GC 回收
_grading_tasks: set[asyncio.Task] = set()


class ExamError(RuntimeError):
    pass


def _apply_difficulty(statement, difficulty: str):
    if difficulty == "easy":
        return statement.where(Question.difficulty <= 2)
    if difficulty == "hard":
        return statement.where(Question.difficulty >= 4)
    if difficulty == "medium":
        return statement.where(Question.difficulty.between(2, 4))
    return statement


def _aware(value):
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


async def generate_exam(
    db: AsyncSession,
    subject: str,
    module: str,
    question_count: int,
    duration_minutes: int,
    difficulty: str,
    *,
    ai_count: int = 0,
    llm: LlmSettings | None = None,
    user_id: str = "local-user",
    tags: list[str] | None = None,
) -> Exam:
    question_count = max(1, min(60, question_count))
    duration_minutes = max(5, min(180, duration_minutes))
    ai_count = max(0, min(ai_count, 30, question_count))

    ai_questions: list[Question] = []
    ai_warning = ""
    if ai_count:
        if llm is None:
            ai_warning = "未配置 LLM，AI 原创题已回退到题库。"
        else:
            kp_rows = list(
                (
                    await db.execute(
                        select(KnowledgePoint).where(
                            KnowledgePoint.module == module,
                            KnowledgePoint.level >= 2,
                        )
                    )
                ).scalars()
            )
            kp_options = [
                {"id": row.id, "name": row.name} for row in kp_rows
            ]
            try:
                result = await generate_ai_questions(
                    llm,
                    subject=subject,
                    module=module,
                    count=ai_count,
                    difficulty=difficulty,
                    kp_options=kp_options,
                )
                for item in result.questions:
                    question = Question(**item)
                    db.add(question)
                    ai_questions.append(question)
                if result.prompt_tokens or result.completion_tokens:
                    await record_usage(
                        db,
                        user_id=user_id,
                        session_id="",
                        role="examiner",
                        model=result.model,
                        prompt_tokens=result.prompt_tokens,
                        completion_tokens=result.completion_tokens,
                        llm=llm,
                        api_base=role_model_config(llm, "examiner").api_base,
                    )
                await db.commit()
            except AiGenerationError as exc:
                await db.rollback()
                ai_warning = f"AI 原创题生成失败，已回退题库：{exc}"
            except Exception as exc:  # noqa: BLE001 - provider errors vary
                await db.rollback()
                ai_warning = f"AI 原创题生成失败，已回退题库：{str(exc)[:160]}"

    # 准入条件：必须是已通过的题，且答案不为空。
    # 空答案的题判不了分，进了试卷只会白送分或污染掌握度。
    base_statement = select(Question).where(
        Question.subject == subject,
        Question.module == module,
        Question.quality_status == "approved",
        Question.type.in_(["single", "multiple", "short"]),
        Question.answer_json.notin_(["{}", "", "null"]),
    )
    tag_filters = [tag.strip() for tag in (tags or []) if tag.strip()]
    if tag_filters:
        # 题目标签是 JSON 数组，SQLite/Postgres 都退化为子串匹配
        for tag in tag_filters:
            base_statement = base_statement.where(
                Question.tags_json.contains(json.dumps(tag, ensure_ascii=False)[1:-1])
            )
    questions = list(
        (await db.execute(_apply_difficulty(base_statement, difficulty))).scalars()
    )
    if len(questions) < question_count:
        questions = list((await db.execute(base_statement)).scalars())
    if not questions and not ai_questions:
        questions = list(
            (
                await db.execute(
                    select(Question).where(
                        Question.quality_status == "approved",
                        Question.answer_json.notin_(["{}", "", "null"]),
                    )
                )
            ).scalars()
        )
    if not questions and not ai_questions:
        raise ExamError("题库还没有可用题目。")

    objective = [q for q in questions if q.type in {"single", "multiple"}]
    short = [q for q in questions if q.type == "short"]
    remaining = max(0, question_count - len(ai_questions))
    short_count = 0
    if not objective and short:
        short_count = min(remaining, len(short))
    elif short and remaining >= 10:
        short_count = min(2, len(short))
    elif short and remaining >= 4:
        short_count = 1

    objective_count = max(0, remaining - short_count)
    rng = random.Random(
        f"{subject}|{module}|{question_count}|{difficulty}|{ai_count}"
    )
    rng.shuffle(objective)
    rng.shuffle(short)

    selected: list[Question] = ai_questions[:ai_count]
    selected.extend(objective[:objective_count])
    selected.extend(short[:short_count])
    if len(selected) < question_count:
        chosen_ids = {question.id for question in selected}
        for question in [*objective, *short]:
            if question.id in chosen_ids:
                continue
            selected.append(question)
            chosen_ids.add(question.id)
            if len(selected) >= question_count:
                break
    selected = selected[:question_count]
    rng.shuffle(selected)
    if not selected:
        raise ExamError("题库还没有可用题目。")

    skill_index = await load_skill_index(db)
    for question in selected:
        if question.skill_id:
            continue
        matches = match_skills(
            f"{question.stem}\n{question.explanation}",
            question.knowledge_point_id,
            skill_index,
            1,
        )
        if matches:
            question.skill_id = matches[0]["id"]
            question.skill_name = matches[0]["name"]
    await db.flush()

    exam = Exam(
        id=uuid.uuid4().hex,
        title=f"{module} · {len(selected)} 题 · {duration_minutes} 分钟",
        subject=subject,
        module=module,
        question_count=len(selected),
        duration_minutes=duration_minutes,
        difficulty=difficulty,
        config_json=json.dumps(
            {
                "subject": subject,
                "module": module,
                "question_count": question_count,
                "duration_minutes": duration_minutes,
                "difficulty": difficulty,
                "ai_count": ai_count,
            },
            ensure_ascii=False,
        ),
        status="ready",
    )
    db.add(exam)
    total_score = 0.0
    for index, question in enumerate(selected):
        score = 8.0 if question.type == "short" else 3.0
        total_score += score
        db.add(
            ExamQuestion(
                id=uuid.uuid4().hex,
                exam_id=exam.id,
                question_id=question.id,
                order_index=index,
                score=score,
            )
        )
    exam.blueprint_json = json.dumps(
        {
            "single": sum(1 for q in selected if q.type == "single"),
            "multiple": sum(1 for q in selected if q.type == "multiple"),
            "short": sum(1 for q in selected if q.type == "short"),
            "ai_generated": sum(1 for q in selected if q.source == "ai"),
            "ai_warning": ai_warning,
            "total_score": total_score,
        },
        ensure_ascii=False,
    )
    await db.commit()
    await db.refresh(exam)
    return exam


def exam_summary(exam: Exam) -> dict:
    try:
        blueprint = json.loads(exam.blueprint_json or "{}")
    except json.JSONDecodeError:
        blueprint = {}
    return {
        "id": exam.id,
        "title": exam.title,
        "subject": exam.subject,
        "module": exam.module,
        "question_count": exam.question_count,
        "duration_minutes": exam.duration_minutes,
        "difficulty": exam.difficulty,
        "ai_generated": int(blueprint.get("ai_generated") or 0),
        "warning": str(blueprint.get("ai_warning") or ""),
        "created_at": exam.created_at.isoformat(),
    }


async def list_exams(db: AsyncSession, limit: int = 20) -> list[dict]:
    result = await db.execute(select(Exam).order_by(Exam.created_at.desc()).limit(limit))
    return [exam_summary(exam) for exam in result.scalars()]


async def get_exam_take(db: AsyncSession, exam_id: str) -> dict:
    exam = await db.get(Exam, exam_id)
    if exam is None:
        raise ExamError("试卷不存在。")
    rows = (
        await db.execute(
            select(ExamQuestion, Question)
            .join(Question, ExamQuestion.question_id == Question.id)
            .where(ExamQuestion.exam_id == exam_id)
            .order_by(ExamQuestion.order_index)
        )
    ).all()
    return {
        **exam_summary(exam),
        "questions": [
            {
                "id": question.id,
                "order_index": link.order_index,
                "type": question.type,
                "stem": question.stem,
                "options": json.loads(question.options_json or "[]"),
                "score": link.score,
                "knowledge_point_id": question.knowledge_point_id,
                "knowledge_point_name": question.knowledge_point_name,
            }
            for link, question in rows
        ],
    }


async def _load_answers(db: AsyncSession, attempt_id: str) -> dict[str, Any]:
    rows = (
        await db.execute(select(Answer).where(Answer.attempt_id == attempt_id))
    ).scalars()
    answers: dict[str, Any] = {}
    for row in rows:
        try:
            answers[row.question_id] = json.loads(row.response_json or "null")
        except json.JSONDecodeError:
            answers[row.question_id] = None
    return answers


async def start_attempt(db: AsyncSession, exam_id: str, user_id: str) -> dict:
    exam = await db.get(Exam, exam_id)
    if exam is None:
        raise ExamError("试卷不存在。")

    existing = (
        await db.execute(
            select(Attempt)
            .where(
                Attempt.exam_id == exam_id,
                Attempt.user_id == user_id,
                Attempt.status == "in_progress",
            )
            .order_by(Attempt.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if existing is None:
        total_score = sum(
            link.score
            for link in (
                await db.execute(
                    select(ExamQuestion).where(ExamQuestion.exam_id == exam_id)
                )
            ).scalars()
        )
        existing = Attempt(
            id=uuid.uuid4().hex,
            exam_id=exam_id,
            user_id=user_id,
            status="in_progress",
            started_at=utcnow(),
            total_score=total_score,
        )
        db.add(existing)
        await db.commit()
        await db.refresh(existing)

    started = _aware(existing.started_at) or utcnow()
    remaining = max(
        0, int(exam.duration_minutes * 60 - (utcnow() - started).total_seconds())
    )
    return {
        "attempt_id": existing.id,
        "status": existing.status,
        "started_at": existing.started_at.isoformat(),
        "remaining_seconds": remaining,
        "exam": await get_exam_take(db, exam_id),
        "answers": await _load_answers(db, existing.id),
    }


async def save_answers(
    db: AsyncSession, attempt_id: str, answers: list[dict]
) -> int:
    attempt = await db.get(Attempt, attempt_id)
    if attempt is None:
        raise ExamError("作答记录不存在。")
    if attempt.status != "in_progress":
        raise ExamError("试卷已提交，不能继续作答。")

    links = (
        await db.execute(
            select(ExamQuestion).where(ExamQuestion.exam_id == attempt.exam_id)
        )
    ).scalars()
    max_scores = {link.question_id: link.score for link in links}

    await db.execute(delete(Answer).where(Answer.attempt_id == attempt_id))
    saved = 0
    for item in answers:
        question_id = str(item.get("question_id", ""))
        if question_id not in max_scores:
            continue
        db.add(
            Answer(
                id=uuid.uuid4().hex,
                attempt_id=attempt_id,
                question_id=question_id,
                response_json=json.dumps(item.get("response"), ensure_ascii=False),
                max_score=max_scores[question_id],
            )
        )
        saved += 1
    await db.commit()
    return saved


async def submit_attempt(
    db: AsyncSession, attempt_id: str, answers: list[dict]
) -> dict:
    """保存答案并把状态推进到 grading，真正的批改交给后台任务。

    批改要给每道错题调一次 LLM 生成讲解，几十秒到几分钟不等。同步等会让
    学生一直停在交卷界面。
    """
    attempt = await db.get(Attempt, attempt_id)
    if attempt is None:
        raise ExamError("作答记录不存在。")
    if attempt.status in ("graded", "grading"):
        return json.loads(attempt.report_json or "{}")

    await save_answers(db, attempt_id, answers)
    attempt = await db.get(Attempt, attempt_id)
    if attempt is None:
        raise ExamError("作答记录不存在。")
    attempt.status = "grading"
    attempt.submitted_at = utcnow()
    await db.commit()

    task = asyncio.create_task(grade_submitted_attempt(attempt_id))
    _grading_tasks.add(task)
    task.add_done_callback(_grading_tasks.discard)
    return {}


async def grade_submitted_attempt(attempt_id: str) -> None:
    """后台批改：判分、生成讲解、写报告，完成后发通知。"""
    from app.db.session import SessionLocal

    async with SessionLocal() as db:
        attempt = await db.get(Attempt, attempt_id)
        if attempt is None or attempt.status != "grading":
            return
        try:
            exam = await db.get(Exam, attempt.exam_id)
            if exam is None:
                raise ExamError("试卷不存在。")

            rows = (
                await db.execute(
                    select(ExamQuestion, Question)
                    .join(
                        Question, ExamQuestion.question_id == Question.id
                    )
                    .where(ExamQuestion.exam_id == attempt.exam_id)
                    .order_by(ExamQuestion.order_index)
                )
            ).all()
            answer_rows = (
                await db.execute(
                    select(Answer).where(Answer.attempt_id == attempt.id)
                )
            ).scalars().all()

            report = await grade_attempt(
                db, attempt, exam, rows, list(answer_rows)
            )
            attempt.status = "graded"
            attempt.score = float(report["score"])
            attempt.total_score = float(report["total_score"])
            attempt.report_json = json.dumps(report, ensure_ascii=False)
            await db.commit()
            await _notify_graded(db, attempt, exam)
        except Exception:
            logger.exception("grading failed for attempt %s", attempt_id)
            attempt.status = "grading_failed"
            await db.commit()


async def _notify_graded(db: AsyncSession, attempt: Attempt, exam: Exam) -> None:
    """批改完成发一条通知，学生从通知点进去看报告。"""
    from app.services.notifications import _create_once

    # 直接从报告取分：attempt 上的 score 列在某些路径下可能还没刷新
    score = 0.0
    total = 0.0
    warning = ""
    try:
        report = json.loads(attempt.report_json or "{}")
        score = float(report.get("score") or 0)
        total = float(report.get("total_score") or 0)
        ungradable = int(report.get("ungradable_count") or 0)
        if ungradable:
            warning = f"（{ungradable} 道题缺少有效答案，未计入）"
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    await _create_once(
        db,
        user_id=attempt.user_id,
        notification_type="exam_graded",
        title="批改完成",
        body=(
            f"《{exam.title}》已批改：{score:.0f}/{total:.0f} 分{warning}。"
            "点这里看逐题讲解和举一反三。"
        ),
        dedupe_key=f"graded:{attempt.id}",
        link=f"/exams/{exam.id}/report/{attempt.id}",
    )
    await db.commit()
    return report


async def get_attempt_state(db: AsyncSession, attempt_id: str) -> dict:
    attempt = await db.get(Attempt, attempt_id)
    if attempt is None:
        raise ExamError("作答记录不存在。")
    exam = await db.get(Exam, attempt.exam_id)
    if exam is None:
        raise ExamError("试卷不存在。")

    if attempt.status == "graded":
        return {
            "attempt_id": attempt.id,
            "status": attempt.status,
            "report": json.loads(attempt.report_json or "{}"),
        }

    started = _aware(attempt.started_at) or utcnow()
    remaining = max(
        0, int(exam.duration_minutes * 60 - (utcnow() - started).total_seconds())
    )
    return {
        "attempt_id": attempt.id,
        "status": attempt.status,
        "started_at": attempt.started_at.isoformat(),
        "remaining_seconds": remaining,
        "exam": await get_exam_take(db, exam.id),
        "answers": await _load_answers(db, attempt.id),
    }


async def get_report(db: AsyncSession, attempt_id: str) -> dict:
    attempt = await db.get(Attempt, attempt_id)
    if attempt is None:
        raise ExamError("作答记录不存在。")
    if attempt.status == "grading":
        return {"status": "grading", "attempt_id": attempt_id}
    if attempt.status == "grading_failed":
        return {
            "status": "failed",
            "attempt_id": attempt_id,
            "message": "批改失败了。可以重新交卷再试一次。",
        }
    if attempt.status != "graded":
        raise ExamError("试卷还没有交卷。")
    report = json.loads(attempt.report_json or "{}")
    report["status"] = "graded"
    report["attempt_id"] = attempt_id
    return report


async def list_attempts(
    db: AsyncSession, user_id: str, limit: int = 20
) -> list[dict]:
    rows = (
        await db.execute(
            select(Attempt, Exam)
            .join(Exam, Attempt.exam_id == Exam.id)
            .where(Attempt.user_id == user_id)
            .order_by(Attempt.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [
        {
            "id": attempt.id,
            "exam_id": attempt.exam_id,
            "exam_title": exam.title,
            "status": attempt.status,
            "score": attempt.score,
            "total_score": attempt.total_score,
            "started_at": attempt.started_at.isoformat(),
            "submitted_at": (
                attempt.submitted_at.isoformat() if attempt.submitted_at else None
            ),
        }
        for attempt, exam in rows
    ]


async def get_latest_attempt_report(
    db: AsyncSession, user_id: str, attempt_id: str = ""
) -> dict:
    """读取已批改试卷的报告。

    学生从报告页跳过来时带着 attempt_id，直接读那一份；否则取最近一次。
    """
    if attempt_id:
        row = (
            await db.execute(
                select(Attempt)
                .where(
                    Attempt.id == attempt_id,
                    Attempt.user_id == user_id,
                    Attempt.status == "graded",
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if row is not None:
            return {
                "status": "success",
                "attempt_id": row.id,
                "report": json.loads(row.report_json or "{}"),
            }

    row = (
        await db.execute(
            select(Attempt, Exam)
            .join(Exam, Attempt.exam_id == Exam.id)
            .where(Attempt.user_id == user_id, Attempt.status == "graded")
            .order_by(Attempt.submitted_at.desc())
            .limit(1)
        )
    ).first()
    if row is None:
        return {"status": "empty", "report": None}
    attempt, _exam = row
    return {
        "status": "success",
        "attempt_id": attempt.id,
        "report": json.loads(attempt.report_json or "{}"),
    }
