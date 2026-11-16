"""Deterministic weekly study-plan generation and task tracking."""

import json
import uuid
from datetime import date, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Plan, PlanTask, utcnow
from app.services.analytics import load_mastery_items
from app.services.settings_service import load_profile_settings

WEEKDAY_LABELS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


class PlanError(RuntimeError):
    pass


def _monday(value: date) -> date:
    return value - timedelta(days=value.weekday())


def _task_dict(task: PlanTask) -> dict:
    return {
        "id": task.id,
        "date": task.date,
        "task_type": task.task_type,
        "title": task.title,
        "knowledge_point_id": task.knowledge_point_id,
        "knowledge_point_name": task.knowledge_point_name,
        "minutes": task.minutes,
        "status": task.status,
    }


def _new_task(
    plan: Plan,
    day: date,
    task_type: str,
    title: str,
    item: dict | None,
    minutes: int,
) -> PlanTask:
    return PlanTask(
        id=uuid.uuid4().hex,
        plan_id=plan.id,
        user_id=plan.user_id,
        date=day.isoformat(),
        task_type=task_type,
        title=title[:255],
        knowledge_point_id=(item or {}).get("knowledge_point_id", ""),
        knowledge_point_name=(item or {}).get("knowledge_point_name", ""),
        minutes=minutes,
        status="pending",
    )


async def generate_week_plan(
    db: AsyncSession, user_id: str, week_start: date | None = None
) -> dict:
    profile = await load_profile_settings(db, user_id)
    start = _monday(week_start or date.today())
    items = await load_mastery_items(db, user_id)

    due = [item for item in items if item["status"] == "due"]
    weak = [
        item
        for item in items
        if item["attempts"] > 0 and item["status"] != "due"
    ]
    weak.sort(
        key=lambda item: (
            item["decayed_score"]
            if item["decayed_score"] is not None
            else item["score"] or 0
        )
    )
    unpracticed = [
        item
        for item in items
        if item["attempts"] == 0
        and (item["level"] >= 3 or item["subject"] == "申论")
    ]

    candidates: list[dict] = []
    seen: set[str] = set()
    for item in [*due, *weak, *unpracticed, *items]:
        key = item["knowledge_point_id"]
        if key in seen:
            continue
        seen.add(key)
        candidates.append(item)
    if not candidates:
        raise PlanError("知识树为空，无法生成计划。")

    week_start_str = start.isoformat()
    plan = (
        await db.execute(
            select(Plan).where(
                Plan.user_id == user_id, Plan.week_start == week_start_str
            )
        )
    ).scalar_one_or_none()

    focus = [item["knowledge_point_name"] for item in (due + weak)[:3]]
    goal = (
        f"{profile.target_exam} · 本周重点：{'、'.join(focus)}"
        if focus
        else f"{profile.target_exam} · 先完成诊断，建立学情档案"
    )

    if plan is None:
        plan = Plan(
            id=uuid.uuid4().hex,
            user_id=user_id,
            week_start=week_start_str,
            goal=goal,
        )
        db.add(plan)
        await db.flush()
    else:
        plan.goal = goal
        await db.execute(delete(PlanTask).where(PlanTask.plan_id == plan.id))

    daily = max(30, min(240, profile.daily_minutes or 120))
    plan.meta_json = json.dumps(
        {"daily_minutes": daily, "generated_at": utcnow().isoformat()},
        ensure_ascii=False,
    )

    review_minutes = 20 if daily >= 90 else 15
    practice_minutes = 35 if daily >= 90 else 25

    tasks: list[PlanTask] = []
    for offset in range(7):
        day = start + timedelta(days=offset)
        review = candidates[(offset * 2) % len(candidates)]
        practice = candidates[(offset * 2 + 1) % len(candidates)]
        material = candidates[(offset * 3 + 2) % len(candidates)]

        tasks.append(
            _new_task(
                plan,
                day,
                "review",
                f"复习：{review['knowledge_point_name']}（知识卡 + 3 题）",
                review,
                review_minutes,
            )
        )
        tasks.append(
            _new_task(
                plan,
                day,
                "practice",
                f"专项练习：{practice['knowledge_point_name']}（10 题）",
                practice,
                practice_minutes,
            )
        )
        if daily >= 75:
            tasks.append(
                _new_task(
                    plan,
                    day,
                    "material",
                    f"阅读知识卡：{material['knowledge_point_name']}",
                    material,
                    15,
                )
            )
        if day.weekday() in (2, 6) and daily >= 100:
            tasks.append(
                _new_task(
                    plan,
                    day,
                    "exam",
                    "限时小卷：资料分析（30 题）",
                    None,
                    35,
                )
            )
        if daily >= 150:
            extra = candidates[(offset * 2 + 3) % len(candidates)]
            tasks.append(
                _new_task(
                    plan,
                    day,
                    "practice",
                    f"加练：{extra['knowledge_point_name']}（10 题）",
                    extra,
                    30,
                )
            )

    db.add_all(tasks)
    await db.commit()
    return await get_week_plan(db, user_id, start)


async def get_week_plan(
    db: AsyncSession, user_id: str, week_start: date | None = None
) -> dict:
    start = _monday(week_start or date.today())
    week_start_str = start.isoformat()
    plan = (
        await db.execute(
            select(Plan).where(
                Plan.user_id == user_id, Plan.week_start == week_start_str
            )
        )
    ).scalar_one_or_none()

    tasks: list[PlanTask] = []
    daily_minutes = 0
    goal = ""
    if plan is not None:
        goal = plan.goal
        try:
            meta = json.loads(plan.meta_json or "{}")
        except json.JSONDecodeError:
            meta = {}
        daily_minutes = int(meta.get("daily_minutes") or 0)
        tasks = list(
            (
                await db.execute(
                    select(PlanTask)
                    .where(PlanTask.plan_id == plan.id)
                    .order_by(PlanTask.date, PlanTask.created_at)
                )
            ).scalars()
        )

    days = []
    for offset in range(7):
        day = start + timedelta(days=offset)
        day_tasks = [
            _task_dict(task) for task in tasks if task.date == day.isoformat()
        ]
        days.append(
            {
                "date": day.isoformat(),
                "weekday": WEEKDAY_LABELS[day.weekday()],
                "tasks": day_tasks,
            }
        )

    done = sum(1 for task in tasks if task.status == "done")
    total = len(tasks)
    return {
        "week_start": week_start_str,
        "week_end": (start + timedelta(days=6)).isoformat(),
        "goal": goal,
        "daily_minutes": daily_minutes,
        "tasks": [_task_dict(task) for task in tasks],
        "days": days,
        "adherence": {
            "done": done,
            "total": total,
            "percent": round(done / total * 100, 1) if total else 0.0,
        },
    }


async def toggle_task(
    db: AsyncSession, task_id: str, user_id: str, done: bool
) -> dict:
    task = await db.get(PlanTask, task_id)
    if task is None or task.user_id != user_id:
        raise PlanError("任务不存在。")
    task.status = "done" if done else "pending"
    task.completed_at = utcnow() if done else None
    await db.commit()
    return _task_dict(task)
