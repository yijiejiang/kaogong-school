from datetime import date

from google.adk.tools import ToolContext

from app.db.session import SessionLocal
from app.services.analytics import build_overview
from app.services.plan import generate_week_plan, get_week_plan
from app.services.settings_service import load_profile_settings


async def get_student_context(tool_context: ToolContext) -> dict:
    """Return a compact profile of the student for the current session.

    Returns the student's name, target exam, exam date, daily study minutes,
    and the current date. Use it before giving personalized advice.
    """
    user_id = tool_context.state.get("user_id", "local-user")
    async with SessionLocal() as db:
        profile = await load_profile_settings(db, user_id)
    return {
        "status": "success",
        "student": profile.model_dump(),
        "note": "学情数据以实际作答记录为准。",
    }


async def get_study_snapshot(tool_context: ToolContext) -> dict:
    """Return real study progress, mastery, weak points and today's plan.

    Use it before giving any judgment about the student's level. If there is
    no attempt history, say so and suggest a diagnostic exam instead of
    inventing numbers.
    """
    user_id = tool_context.state.get("user_id", "local-user")
    async with SessionLocal() as db:
        profile = await load_profile_settings(db, user_id)
        overview = await build_overview(db, user_id)
        plan = await get_week_plan(db, user_id)

    stats = overview["stats"]
    today = date.today().isoformat()
    today_tasks = [
        task for task in plan.get("tasks", []) if task.get("date") == today
    ]
    return {
        "status": "success",
        "profile": profile.model_dump(),
        "attempts": stats["graded_attempts"],
        "questions": stats["questions"],
        "accuracy": stats["accuracy"],
        "study_minutes": stats["study_minutes"],
        "coverage": stats["coverage"],
        "practiced_kps": stats["practiced_kps"],
        "total_kps": stats["total_kps"],
        "weak_points": overview["weak_points"][:5],
        "today_tasks": today_tasks,
        "plan_goal": plan.get("goal", ""),
        "alerts": overview["alerts"],
        "message": (
            "下面是从真实作答记录统计出的学情。"
            if stats["graded_attempts"]
            else "还没有做题记录。建议先完成一次诊断小卷，再建立学情档案。"
        ),
    }


async def generate_study_plan(tool_context: ToolContext) -> dict:
    """Generate or refresh this week's study plan from the real mastery data."""
    user_id = tool_context.state.get("user_id", "local-user")
    async with SessionLocal() as db:
        plan = await generate_week_plan(db, user_id)
    return {
        "status": "success",
        "plan": plan,
        "message": "本周计划已生成。",
    }
