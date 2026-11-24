from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.exams.service import (
    ExamError,
    exam_summary,
    generate_exam,
    get_attempt_state,
    get_exam_take,
    get_report,
    list_attempts,
    list_exams,
    save_answers,
    start_attempt,
    submit_attempt,
)
from app.schemas.exams import (
    AnswerSaveRequest,
    AttemptReport,
    AttemptStart,
    AttemptState,
    AttemptSummary,
    ExamGenerateRequest,
    ExamOut,
    ExamTake,
    SubmitRequest,
)
from app.services.settings_service import load_llm_settings

router = APIRouter(prefix="/api", tags=["exams"])


@router.post("/exams/generate", response_model=ExamOut)
async def generate(
    payload: ExamGenerateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExamOut:
    llm = await load_llm_settings(db)
    try:
        exam = await generate_exam(
            db,
            payload.subject,
            payload.module,
            payload.question_count,
            payload.duration_minutes,
            payload.difficulty,
            ai_count=payload.ai_count,
            llm=llm,
            user_id=payload.user_id,
            tags=payload.tags,
        )
    except ExamError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ExamOut(**exam_summary(exam))


@router.get("/exams", response_model=list[ExamOut])
async def exams(db: Annotated[AsyncSession, Depends(get_db)]) -> list[ExamOut]:
    return [ExamOut(**item) for item in await list_exams(db)]


@router.get("/exams/{exam_id}", response_model=ExamTake)
async def exam_detail(
    exam_id: str, db: Annotated[AsyncSession, Depends(get_db)]
) -> ExamTake:
    try:
        data = await get_exam_take(db, exam_id)
    except ExamError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ExamTake(**data)


@router.post("/exams/{exam_id}/start", response_model=AttemptStart)
async def start(
    exam_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: str = "local-user",
) -> AttemptStart:
    try:
        data = await start_attempt(db, exam_id, user_id)
    except ExamError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AttemptStart(**data)


@router.get("/attempts", response_model=list[AttemptSummary])
async def attempts(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: str = "local-user",
) -> list[AttemptSummary]:
    return [
        AttemptSummary(**item) for item in await list_attempts(db, user_id)
    ]


@router.get("/attempts/{attempt_id}", response_model=AttemptState)
async def attempt_state(
    attempt_id: str, db: Annotated[AsyncSession, Depends(get_db)]
) -> AttemptState:
    try:
        data = await get_attempt_state(db, attempt_id)
    except ExamError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AttemptState(**data)


@router.post("/attempts/{attempt_id}/answers")
async def save(
    attempt_id: str,
    payload: AnswerSaveRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    try:
        saved = await save_answers(
            db, attempt_id, [item.model_dump() for item in payload.answers]
        )
    except ExamError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True, "saved": saved}


@router.post("/attempts/{attempt_id}/submit", response_model=AttemptReport)
async def submit(
    attempt_id: str,
    payload: SubmitRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AttemptReport:
    try:
        report = await submit_attempt(
            db, attempt_id, [item.model_dump() for item in payload.answers]
        )
    except ExamError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return AttemptReport(**report)


@router.get("/attempts/{attempt_id}/report", response_model=AttemptReport)
async def report(
    attempt_id: str, db: Annotated[AsyncSession, Depends(get_db)]
) -> AttemptReport:
    try:
        data = await get_report(db, attempt_id)
    except ExamError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return AttemptReport(**data)
