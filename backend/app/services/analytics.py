"""Real study analytics, mastery v2, and weekly report."""

import math
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Answer,
    Attempt,
    KnowledgePoint,
    Mastery,
    PlanTask,
    utcnow,
)
from app.services.settings_service import load_profile_settings


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _mastery_item(point: KnowledgePoint, row: Mastery | None) -> dict:
    score = round(row.score, 1) if row and row.score is not None else None
    attempts = row.attempts if row and row.attempts is not None else 0
    correct = row.correct if row and row.correct is not None else 0
    last = _aware(row.last_practiced) if row else None
    confidence = round(1 - math.exp(-attempts / 8), 2) if attempts else 0.0

    days_since = (utcnow() - last).days if last else None
    decayed_score = (
        round(score * math.exp(-days_since / 45), 1)
        if score is not None and days_since is not None
        else score
    )

    due_at = None
    status = "unpracticed"
    if last and score is not None:
        interval = 1 if score < 40 else 3 if score < 60 else 7 if score < 80 else 14
        due = last + timedelta(days=interval)
        due_at = due.date().isoformat()
        if due <= utcnow():
            status = "due"
        elif score >= 80:
            status = "strong"
        elif score < 60:
            status = "learning"
        else:
            status = "practicing"

    return {
        "knowledge_point_id": point.id,
        "knowledge_point_name": point.name,
        "subject": point.subject,
        "module": point.module,
        "level": point.level,
        "score": score,
        "decayed_score": decayed_score,
        "confidence": confidence,
        "attempts": attempts,
        "correct": correct,
        "last_practiced": last.isoformat() if last else None,
        "due_at": due_at,
        "status": status,
    }


async def load_mastery_items(db: AsyncSession, user_id: str) -> list[dict]:
    mastery_rows = (
        await db.execute(select(Mastery).where(Mastery.user_id == user_id))
    ).scalars().all()
    mastery_by_id = {row.knowledge_point_id: row for row in mastery_rows}
    points = (
        await db.execute(
            select(KnowledgePoint)
            .where(KnowledgePoint.level >= 2)
            .order_by(KnowledgePoint.sort_order, KnowledgePoint.id)
        )
    ).scalars().all()
    return [_mastery_item(point, mastery_by_id.get(point.id)) for point in points]


def _module_scores(items: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str], list[dict]] = {}
    for item in items:
        key = (item["subject"], item["module"])
        if not key[1]:
            continue
        groups.setdefault(key, []).append(item)

    modules: list[dict] = []
    for (subject, module_name), children in groups.items():
        attempted = [
            item
            for item in children
            if item["attempts"] > 0 and item["score"] is not None
        ]
        total_attempts = sum(item["attempts"] for item in attempted)
        if total_attempts:
            weighted = sum(item["score"] * item["attempts"] for item in attempted)
            score = round(weighted / total_attempts, 1)
        else:
            score = None
        modules.append(
            {
                "subject": subject,
                "module": module_name,
                "score": score,
                "attempts": total_attempts,
                "kp_count": len(children),
                "practiced": len(attempted),
            }
        )
    modules.sort(key=lambda item: (item["subject"], item["module"]))
    return modules


async def _stats(db: AsyncSession, user_id: str, items: list[dict]) -> dict:
    attempts = (
        await db.execute(select(Attempt).where(Attempt.user_id == user_id))
    ).scalars().all()
    graded = [attempt for attempt in attempts if attempt.status == "graded"]

    score_sum = sum(attempt.score or 0 for attempt in graded)
    total_sum = sum(attempt.total_score or 0 for attempt in graded)
    accuracy = round(score_sum / total_sum * 100, 1) if total_sum else 0.0

    questions = 0
    if graded:
        graded_ids = [attempt.id for attempt in graded]
        questions = (
            await db.execute(
                select(func.count(Answer.id)).where(
                    Answer.attempt_id.in_(graded_ids)
                )
            )
        ).scalar() or 0

    study_minutes = 0.0
    for attempt in graded:
        started = _aware(attempt.started_at)
        submitted = _aware(attempt.submitted_at)
        if started and submitted:
            study_minutes += max(0.0, (submitted - started).total_seconds() / 60)

    practiced = sum(1 for item in items if item["attempts"] > 0)
    total = len(items)
    return {
        "attempts": len(attempts),
        "graded_attempts": len(graded),
        "questions": int(questions),
        "accuracy": accuracy,
        "study_minutes": round(study_minutes),
        "coverage": round(practiced / total * 100, 1) if total else 0.0,
        "practiced_kps": practiced,
        "total_kps": total,
    }


async def _trend(db: AsyncSession, user_id: str, days: int = 14) -> list[dict]:
    today = date.today()
    start = today - timedelta(days=days - 1)
    buckets = {
        (start + timedelta(days=offset)).isoformat(): {
            "date": (start + timedelta(days=offset)).isoformat(),
            "label": (start + timedelta(days=offset)).strftime("%m-%d"),
            "attempts": 0,
            "score": 0.0,
            "total_score": 0.0,
            "accuracy": 0.0,
        }
        for offset in range(days)
    }

    attempts = (
        await db.execute(
            select(Attempt).where(
                Attempt.user_id == user_id, Attempt.status == "graded"
            )
        )
    ).scalars().all()
    for attempt in attempts:
        submitted = _aware(attempt.submitted_at)
        if not submitted:
            continue
        key = submitted.date().isoformat()
        bucket = buckets.get(key)
        if bucket is None:
            continue
        bucket["attempts"] += 1
        bucket["score"] += attempt.score or 0
        bucket["total_score"] += attempt.total_score or 0

    for bucket in buckets.values():
        if bucket["total_score"]:
            bucket["accuracy"] = round(
                bucket["score"] / bucket["total_score"] * 100, 1
            )
        bucket["score"] = round(bucket["score"], 1)
        bucket["total_score"] = round(bucket["total_score"], 1)
    return list(buckets.values())


def _weak_points(items: list[dict], limit: int = 6) -> list[dict]:
    practiced = [
        item
        for item in items
        if item["attempts"] > 0 and item["score"] is not None
    ]
    practiced.sort(
        key=lambda item: (
            item["decayed_score"]
            if item["decayed_score"] is not None
            else item["score"]
        )
    )
    return practiced[:limit]


def _alerts(profile, items: list[dict], stats: dict) -> list[dict]:
    alerts: list[dict] = []
    exam_date = _parse_date(profile.exam_date)
    if exam_date:
        days = (exam_date - date.today()).days
        if days >= 0:
            alerts.append(
                {
                    "level": "info",
                    "text": f"距{profile.target_exam}考试还有 {days} 天",
                }
            )
        else:
            alerts.append(
                {
                    "level": "warning",
                    "text": "考试日期已过，建议更新目标考试日期",
                }
            )

    due = [item for item in items if item["status"] == "due"]
    if due:
        alerts.append(
            {
                "level": "warning",
                "text": f"今天有 {len(due)} 个知识点到期，建议优先复习",
            }
        )

    if stats["graded_attempts"] == 0:
        alerts.append(
            {
                "level": "info",
                "text": "还没有做过套卷，建议先完成一次诊断小卷",
            }
        )
    elif stats["practiced_kps"] < stats["total_kps"]:
        alerts.append(
            {
                "level": "info",
                "text": f"还有 {stats['total_kps'] - stats['practiced_kps']} 个知识点没有练习",
            }
        )

    if stats["graded_attempts"] and stats["study_minutes"] == 0:
        alerts.append(
            {"level": "info", "text": "最近没有记录到学习时长，做套卷时会自动统计"}
        )
    return alerts


async def build_overview(db: AsyncSession, user_id: str) -> dict:
    profile = await load_profile_settings(db, user_id)
    items = await load_mastery_items(db, user_id)
    stats = await _stats(db, user_id, items)
    modules = _module_scores(items)
    trend = await _trend(db, user_id)
    weak = _weak_points(items)
    alerts = _alerts(profile, items, stats)
    exam_date = _parse_date(profile.exam_date)
    countdown = (exam_date - date.today()).days if exam_date else None
    return {
        "profile": profile.model_dump(),
        "exam_countdown_days": countdown,
        "stats": stats,
        "alerts": alerts,
        "modules": modules,
        "mastery": items,
        "weak_points": weak,
        "trend": trend,
    }


async def build_weekly_report(db: AsyncSession, user_id: str) -> dict:
    today = date.today()
    start = today - timedelta(days=6)
    attempts = (
        await db.execute(
            select(Attempt).where(
                Attempt.user_id == user_id, Attempt.status == "graded"
            )
        )
    ).scalars().all()
    period_attempts = []
    for attempt in attempts:
        submitted = _aware(attempt.submitted_at)
        if submitted and start <= submitted.date() <= today:
            period_attempts.append(attempt)

    attempt_ids = [attempt.id for attempt in period_attempts]
    questions = 0
    wrong_count = 0
    if attempt_ids:
        questions = (
            await db.execute(
                select(func.count(Answer.id)).where(
                    Answer.attempt_id.in_(attempt_ids)
                )
            )
        ).scalar() or 0
        wrong_count = (
            await db.execute(
                select(func.count(Answer.id)).where(
                    Answer.attempt_id.in_(attempt_ids),
                    Answer.is_correct.is_(False),
                )
            )
        ).scalar() or 0

    score_sum = sum(attempt.score or 0 for attempt in period_attempts)
    total_sum = sum(attempt.total_score or 0 for attempt in period_attempts)
    accuracy = round(score_sum / total_sum * 100, 1) if total_sum else 0.0
    study_minutes = 0.0
    for attempt in period_attempts:
        started = _aware(attempt.started_at)
        submitted = _aware(attempt.submitted_at)
        if started and submitted:
            study_minutes += max(0.0, (submitted - started).total_seconds() / 60)

    tasks = (
        await db.execute(
            select(PlanTask).where(
                PlanTask.user_id == user_id,
                PlanTask.date >= start.isoformat(),
                PlanTask.date <= today.isoformat(),
            )
        )
    ).scalars().all()
    plan_total = len(tasks)
    plan_done = sum(1 for task in tasks if task.status == "done")

    items = await load_mastery_items(db, user_id)
    weak = _weak_points(items, limit=3)

    if not period_attempts:
        summary = "本周还没有练习记录。建议先完成一次诊断小卷，再按薄弱点生成计划。"
    else:
        parts = [
            (
                f"本周完成 {len(period_attempts)} 次练习，共 {questions} 题，"
                f"正确率 {accuracy}%。"
            )
        ]
        if weak:
            names = "、".join(item["knowledge_point_name"] for item in weak)
            parts.append(f"最需要关注：{names}。")
        if plan_total:
            parts.append(f"本周计划完成 {plan_done}/{plan_total} 项。")
        parts.append(f"累计学习约 {round(study_minutes)} 分钟。")
        summary = " ".join(parts)

    return {
        "period_start": start.isoformat(),
        "period_end": today.isoformat(),
        "attempts": len(period_attempts),
        "questions": int(questions),
        "accuracy": accuracy,
        "study_minutes": round(study_minutes),
        "wrong_count": int(wrong_count),
        "plan_done": plan_done,
        "plan_total": plan_total,
        "weak_points": weak,
        "summary": summary,
    }
