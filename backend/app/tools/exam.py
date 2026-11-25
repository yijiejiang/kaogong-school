"""Exam generation and grading tools for the chat agents."""

import json

from google.adk.tools import ToolContext

from app.db.session import SessionLocal
from app.exams.service import (
    ExamError,
)
from app.exams.service import (
    generate_exam as create_exam,
)
from app.exams.service import (
    get_latest_attempt_report as latest_report,
)
from app.services.settings_service import load_llm_settings

DIFFICULTY_LABELS = {
    "easy": "简单",
    "medium": "中等",
    "hard": "困难",
    "mixed": "混合",
}


async def generate_exam(
    subject: str,
    module: str,
    question_count: int,
    minutes: int,
    difficulty: str,
    tool_context: ToolContext,
    ai_count: int = 0,
    tags: list[str] | None = None,
) -> dict:
    """Generate a real exam from the question bank and return an exam card.

    Args:
        subject: "行测" or "申论".
        module: Module name such as "资料分析".
        question_count: Number of questions, 1-60.
        minutes: Time limit in minutes.
        difficulty: "easy", "medium", "hard", or "mixed".
        ai_count: How many questions should be AI-authored, 0-30. Use 0 unless
            the student explicitly asks for AI 原创题.
        tags: Optional fine-grained question tags from the question bank,
            e.g. ["牛吃草", "概率问题"]. Only pass tags the student named.
    """
    user_id = tool_context.state.get("user_id", "local-user")
    async with SessionLocal() as db:
        llm = await load_llm_settings(db)
        try:
            exam = await create_exam(
                db,
                subject,
                module,
                question_count,
                minutes,
                difficulty,
                ai_count=ai_count,
                llm=llm,
                user_id=user_id,
                tags=tags,
            )
        except ExamError as exc:
            return {"status": "error", "message": str(exc)}

    try:
        blueprint = json.loads(exam.blueprint_json or "{}")
    except json.JSONDecodeError:
        blueprint = {}
    warning = str(blueprint.get("ai_warning") or "")
    message = "试卷已生成，点击卡片开始考试。"
    if warning:
        message = f"{message}（{warning}）"

    return {
        "status": "success",
        "exam_id": exam.id,
        "title": exam.title,
        "message": message,
        "ui": {
            "type": "exam_card",
            "exam_id": exam.id,
            "title": exam.title,
            "subtitle": (
                f"{exam.question_count} 题 · {exam.duration_minutes} 分钟 · "
                f"{DIFFICULTY_LABELS.get(exam.difficulty, exam.difficulty)}"
            ),
            "questions": exam.question_count,
            "duration_minutes": exam.duration_minutes,
            "subject": exam.subject,
            "module": exam.module,
            "difficulty": exam.difficulty,
            "ai_generated": int(blueprint.get("ai_generated") or 0),
            "warning": warning,
        },
    }


async def get_latest_attempt_report(tool_context: ToolContext) -> dict:
    """Return the graded attempt report the student is looking at.

    学生从报告页进入对话时，会话里带了 attempt_id，优先读那一份；
    否则取最近一次已批改试卷。没有记录时返回 empty，不要编造分数。
    """
    user_id = tool_context.state.get("user_id", "local-user")
    attempt_id = tool_context.state.get("active_attempt_id", "")
    async with SessionLocal() as db:
        return await latest_report(db, user_id, attempt_id)
