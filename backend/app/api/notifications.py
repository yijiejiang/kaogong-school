from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.notifications import NotificationList, NotificationOut
from app.services.notifications import (
    ensure_daily_notifications,
    list_notifications,
    mark_all_read,
    mark_read,
)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=NotificationList)
async def get_notifications(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: str = "local-user",
    limit: int = 20,
) -> NotificationList:
    return NotificationList(**await list_notifications(db, user_id, limit))


@router.patch("/{notification_id}/read", response_model=NotificationOut)
async def read_notification(
    notification_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: str = "local-user",
) -> NotificationOut:
    data = await mark_read(db, notification_id, user_id)
    if data is None:
        raise HTTPException(status_code=404, detail="通知不存在。")
    return NotificationOut(**data)


@router.post("/read-all")
async def read_all(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: str = "local-user",
) -> dict:
    updated = await mark_all_read(db, user_id)
    return {"ok": True, "updated": updated}


@router.post("/run")
async def run_notifications(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: str = "local-user",
) -> dict:
    created = await ensure_daily_notifications(db, user_id)
    return {"ok": True, "created": created}
