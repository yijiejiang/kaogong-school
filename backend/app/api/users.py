from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select, union
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import AppSetting, Attempt, Mastery, Plan
from app.db.session import get_db
from app.services.settings_service import load_profile_settings

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("")
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    attempts = select(Attempt.user_id).distinct()
    mastery = select(Mastery.user_id).distinct()
    plans = select(Plan.user_id).distinct()
    ids = {
        row for row in (await db.execute(union(attempts, mastery, plans))).scalars()
    }
    profile_rows = (
        await db.execute(
            select(AppSetting.key).where(AppSetting.key.like("profile:%"))
        )
    ).scalars()
    ids.update(key.split(":", 1)[1] for key in profile_rows if ":" in key)
    ids.add(get_settings().default_user_id)
    ids.discard("")

    users: list[dict] = []
    for user_id in ids:
        profile = await load_profile_settings(db, user_id)
        count = len(
            (
                await db.execute(
                    select(Attempt.id).where(Attempt.user_id == user_id)
                )
            ).scalars().all()
        )
        users.append(
            {
                "id": user_id,
                "name": profile.name,
                "target_exam": profile.target_exam,
                "exam_date": profile.exam_date,
                "attempts": count,
                "is_default": user_id == get_settings().default_user_id,
            }
        )
    users.sort(key=lambda item: (not item["is_default"], item["id"]))
    return users
