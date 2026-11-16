from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.analytics import (
    PlanGenerateRequest,
    PlanTaskOut,
    TaskToggleRequest,
    WeekPlanOut,
)
from app.services.plan import PlanError, generate_week_plan, get_week_plan, toggle_task

router = APIRouter(prefix="/api/plan", tags=["plan"])


def _week_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="week_start 格式应为 YYYY-MM-DD。"
        ) from exc


@router.get("/week", response_model=WeekPlanOut)
async def week_plan(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: str = "local-user",
    week_start: str | None = None,
) -> WeekPlanOut:
    return WeekPlanOut(
        **await get_week_plan(db, user_id, _week_date(week_start))
    )


@router.post("/generate", response_model=WeekPlanOut)
async def generate_plan(
    payload: PlanGenerateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: str = "local-user",
) -> WeekPlanOut:
    try:
        data = await generate_week_plan(
            db, user_id, _week_date(payload.week_start)
        )
    except PlanError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WeekPlanOut(**data)


@router.patch("/tasks/{task_id}", response_model=PlanTaskOut)
async def toggle(
    task_id: str,
    payload: TaskToggleRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: str = "local-user",
) -> PlanTaskOut:
    try:
        data = await toggle_task(db, task_id, user_id, payload.done)
    except PlanError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PlanTaskOut(**data)
