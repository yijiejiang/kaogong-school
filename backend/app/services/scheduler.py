"""In-process scheduler for proactive study notifications."""

import asyncio
import logging

from sqlalchemy import select, union

from app.config import get_settings
from app.db.models import Attempt, Mastery, Plan
from app.db.session import SessionLocal
from app.services.notifications import ensure_daily_notifications

logger = logging.getLogger(__name__)


async def _active_users(db) -> set[str]:
    statements = (
        select(Attempt.user_id).distinct(),
        select(Mastery.user_id).distinct(),
        select(Plan.user_id).distinct(),
    )
    ids = {row for row in (await db.execute(union(*statements))).scalars()}
    ids.add(get_settings().default_user_id)
    ids.discard("")
    return ids


async def notification_loop() -> None:
    while True:
        try:
            async with SessionLocal() as db:
                for user_id in await _active_users(db):
                    await ensure_daily_notifications(db, user_id)
        except Exception:
            logger.exception("notification scheduler failed")
        await asyncio.sleep(1800)
