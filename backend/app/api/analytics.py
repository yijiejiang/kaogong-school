from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.analytics import OverviewOut, WeeklyReportOut
from app.services.analytics import build_overview, build_weekly_report
from app.services.usage import build_usage_summary

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/overview", response_model=OverviewOut)
async def overview(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: str = "local-user",
) -> OverviewOut:
    return OverviewOut(**await build_overview(db, user_id))


@router.get("/weekly-report", response_model=WeeklyReportOut)
async def weekly_report(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: str = "local-user",
) -> WeeklyReportOut:
    return WeeklyReportOut(**await build_weekly_report(db, user_id))


@router.get("/usage")
async def usage(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: str = "local-user",
    days: int = 14,
) -> dict:
    return await build_usage_summary(db, user_id, days)


@router.get("/billing")
async def billing(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: str = "local-user",
) -> dict:
    from app.services.usage import build_billing_overview

    return await build_billing_overview(db, user_id)
