"""Question bank: browse, tag, edit and re-extract uploaded questions."""

import json
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Material, Question
from app.db.session import get_db
from app.services.question_extraction import extract_questions
from app.services.settings_service import load_llm_settings

router = APIRouter(prefix="/api/questions", tags=["questions"])


class QuestionOut(BaseModel):
    id: str
    type: str
    subject: str
    module: str
    knowledge_point_id: str = ""
    knowledge_point_name: str = ""
    stem: str
    options: list[dict] = Field(default_factory=list)
    answer: str = ""
    explanation: str = ""
    difficulty: int = 3
    source: str = ""
    material_id: str = ""
    tags: list[str] = Field(default_factory=list)
    created_at: datetime


class QuestionUpdate(BaseModel):
    type: str | None = None
    subject: str | None = None
    module: str | None = None
    stem: str | None = None
    options: list[dict] | None = None
    answer: str | None = None
    explanation: str | None = None
    difficulty: int | None = None
    tags: list[str] | None = None


def _loads(value: str, default):
    try:
        parsed = json.loads(value or "")
    except json.JSONDecodeError:
        return default
    return parsed


def _question_out(row: Question) -> QuestionOut:
    options = _loads(row.options_json, [])
    answer = _loads(row.answer_json, {})
    return QuestionOut(
        id=row.id,
        type=row.type,
        subject=row.subject,
        module=row.module,
        knowledge_point_id=row.knowledge_point_id,
        knowledge_point_name=row.knowledge_point_name,
        stem=row.stem,
        options=options if isinstance(options, list) else [],
        answer=str(answer.get("value") or "") if isinstance(answer, dict) else "",
        explanation=row.explanation,
        difficulty=row.difficulty,
        source=row.source,
        material_id=row.material_id,
        tags=_loads(row.tags_json, []),
        created_at=row.created_at,
    )


@router.get("", response_model=list[QuestionOut])
async def list_questions(
    db: Annotated[AsyncSession, Depends(get_db)],
    tag: str = "",
    module: str = "",
    subject: str = "",
    material_id: str = "",
    search: str = "",
    limit: int = 200,
) -> list[QuestionOut]:
    statement = select(Question).order_by(Question.created_at.desc())
    if tag:
        statement = statement.where(
            Question.tags_json.contains(json.dumps(tag, ensure_ascii=False)[1:-1])
        )
    if module:
        statement = statement.where(Question.module == module)
    if subject:
        statement = statement.where(Question.subject == subject)
    if material_id:
        statement = statement.where(Question.material_id == material_id)
    if search:
        statement = statement.where(Question.stem.contains(search))
    rows = (
        await db.execute(statement.limit(max(1, min(limit, 500))))
    ).scalars()
    return [_question_out(row) for row in rows]


@router.get("/tags")
async def list_tags(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """所有标签及使用次数，用于筛选和出卷。"""
    rows = list((await db.execute(select(Question))).scalars())
    counts: dict[str, int] = {}
    modules: dict[str, int] = {}
    for row in rows:
        for tag in _loads(row.tags_json, []):
            if not isinstance(tag, str) or not tag.strip():
                continue
            counts[tag] = counts.get(tag, 0) + 1
        if row.module:
            modules[row.module] = modules.get(row.module, 0) + 1
    tags = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return {
        "total": len(rows),
        "tags": [{"tag": tag, "count": count} for tag, count in tags],
        "modules": [
            {"module": module, "count": count}
            for module, count in sorted(
                modules.items(), key=lambda item: item[1], reverse=True
            )
        ],
    }


@router.patch("/{question_id}", response_model=QuestionOut)
async def update_question(
    question_id: str,
    payload: QuestionUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> QuestionOut:
    row = await db.get(Question, question_id)
    if row is None:
        raise HTTPException(status_code=404, detail="题目不存在。")
    data = payload.model_dump(exclude_unset=True)
    for field in ("type", "subject", "module", "stem", "explanation"):
        if field in data and data[field] is not None:
            setattr(row, field, str(data[field]))
    if data.get("difficulty") is not None:
        row.difficulty = max(1, min(5, int(data["difficulty"])))
    if data.get("options") is not None:
        row.options_json = json.dumps(data["options"], ensure_ascii=False)
    if data.get("answer") is not None:
        value = str(data["answer"]).strip().upper()
        row.answer_json = json.dumps(
            {"value": value} if value else {}, ensure_ascii=False
        )
    if data.get("tags") is not None:
        tags = [
            str(tag).strip()[:32]
            for tag in data["tags"]
            if str(tag).strip()
        ][:10]
        row.tags_json = json.dumps(tags, ensure_ascii=False)
    await db.commit()
    await db.refresh(row)
    return _question_out(row)


@router.delete("/{question_id}")
async def delete_question(
    question_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    row = await db.get(Question, question_id)
    if row is None:
        raise HTTPException(status_code=404, detail="题目不存在。")
    await db.delete(row)
    await db.commit()
    return {"ok": True}


@router.post("/extract/{material_id}")
async def extract_from_material(
    material_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    material = await db.get(Material, material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="资料不存在。")
    llm = await load_llm_settings(db)
    result = await extract_questions(db, material_id, llm)
    return {"status": "success", **result}


@router.get("/stats")
async def question_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    total = (await db.execute(select(func.count()).select_from(Question))).scalar()
    by_source = (
        await db.execute(
            select(Question.source, func.count()).group_by(Question.source)
        )
    ).all()
    return {
        "total": total or 0,
        "by_source": [
            {"source": source or "seed", "count": count}
            for source, count in by_source
        ],
    }
