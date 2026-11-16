from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health(db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    database_ok = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - health must report rather than raise
        database_ok = False

    return {
        "status": "ok" if database_ok else "degraded",
        "database": database_ok,
        "time": datetime.now(UTC).isoformat(),
    }
