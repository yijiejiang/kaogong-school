"""Daily and weekly proactive notifications."""

import uuid
from datetime import date

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Notification
from app.services.analytics import build_overview, build_weekly_report
from app.services.plan import generate_week_plan, get_week_plan
from app.services.settings_service import load_profile_settings


def _notification_dict(item: Notification) -> dict:
    return {
        "id": item.id,
        "type": item.type,
        "title": item.title,
        "body": item.body,
        "link": item.link or "",
        "read": bool(item.read),
        "created_at": item.created_at.isoformat(),
    }


async def _create_once(
    db: AsyncSession,
    user_id: str,
    notification_type: str,
    title: str,
    body: str,
    dedupe_key: str,
    link: str = "",
) -> bool:
    existing = (
        await db.execute(
            select(Notification).where(Notification.dedupe_key == dedupe_key)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return False
    db.add(
        Notification(
            id=uuid.uuid4().hex,
            user_id=user_id,
            type=notification_type,
            title=title,
            body=body,
            link=link,
            dedupe_key=dedupe_key,
        )
    )
    return True


async def ensure_daily_notifications(db: AsyncSession, user_id: str) -> int:
    today = date.today().isoformat()
    profile = await load_profile_settings(db, user_id)

    plan = await get_week_plan(db, user_id)
    if not plan.get("tasks"):
        plan = await generate_week_plan(db, user_id)
    today_tasks = [
        task for task in plan.get("tasks", []) if task.get("date") == today
    ]

    overview = await build_overview(db, user_id)
    due = [
        item
        for item in overview.get("mastery", [])
        if item.get("status") == "due"
    ]
    countdown = overview.get("exam_countdown_days")

    parts = [f"今天有 {len(today_tasks)} 个学习任务"]
    if due:
        parts.append(f"{len(due)} 个知识点到期")
    if countdown is not None and countdown >= 0:
        parts.append(f"距{profile.target_exam}考试 {countdown} 天")
    body = "，".join(parts) + "。"

    created = 0
    if await _create_once(
        db,
        user_id,
        "daily_plan",
        "今日学习提醒",
        body,
        f"{user_id}:{today}:daily_plan",
    ):
        created += 1

    if date.today().weekday() == 0:
        report = await build_weekly_report(db, user_id)
        if await _create_once(
            db,
            user_id,
            "weekly_report",
            "本周周报",
            report["summary"],
            f"{user_id}:{today}:weekly_report",
        ):
            created += 1

    await db.commit()
    return created


async def list_notifications(
    db: AsyncSession, user_id: str, limit: int = 20
) -> dict:
    rows = (
        await db.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    unread = (
        await db.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id,
                Notification.read.is_(False),
            )
        )
    ).scalar() or 0
    return {
        "items": [_notification_dict(item) for item in rows],
        "unread": int(unread),
    }


async def mark_read(
    db: AsyncSession, notification_id: str, user_id: str
) -> dict | None:
    item = await db.get(Notification, notification_id)
    if item is None or item.user_id != user_id:
        return None
    item.read = True
    await db.commit()
    return _notification_dict(item)


async def mark_all_read(db: AsyncSession, user_id: str) -> int:
    result = await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read.is_(False))
        .values(read=True)
    )
    await db.commit()
    return int(result.rowcount or 0)
