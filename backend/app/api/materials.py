import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Job, Material
from app.db.session import get_db
from app.rag.embeddings import get_embedding_service
from app.rag.index import search_knowledge
from app.rag.parsers import ParseError, UnsafeUrl
from app.schemas.materials import (
    ChunkOut,
    JobOut,
    KnowledgeCardHit,
    MaterialDetail,
    MaterialOut,
    SearchHit,
    SearchRequest,
    SearchResponse,
    UrlImportRequest,
)
from app.services.ingestion import (
    create_sample_material,
    create_uploaded_material,
    create_url_material,
    delete_material,
    reindex_material,
)
from app.services.settings_service import load_llm_settings

router = APIRouter(prefix="/api", tags=["materials"])


@router.post("/materials/upload", response_model=MaterialOut)
async def upload_material(
    file: Annotated[UploadFile, File(...)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MaterialOut:
    try:
        material = await create_uploaded_material(db, file)
    except ParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MaterialOut.model_validate(material)


@router.post("/materials/import-url", response_model=MaterialOut)
async def import_url(
    payload: UrlImportRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MaterialOut:
    try:
        material = await create_url_material(db, payload.url)
    except UnsafeUrl as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MaterialOut.model_validate(material)


@router.post("/materials/seed-sample", response_model=MaterialOut)
async def seed_sample(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MaterialOut:
    try:
        material = await create_sample_material(db)
    except ParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MaterialOut.model_validate(material)


@router.get("/materials", response_model=list[MaterialOut])
async def list_materials(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[MaterialOut]:
    result = await db.execute(select(Material).order_by(Material.created_at.desc()))
    return [MaterialOut.model_validate(material) for material in result.scalars()]


@router.get("/materials/{material_id}", response_model=MaterialDetail)
async def get_material(
    material_id: str, db: Annotated[AsyncSession, Depends(get_db)]
) -> MaterialDetail:
    material = await db.get(Material, material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="资料不存在。")

    result = await db.execute(
        select(Chunk)
        .where(Chunk.material_id == material_id)
        .order_by(Chunk.chunk_index)
        .limit(200)
    )
    chunks: list[ChunkOut] = []
    for chunk in result.scalars():
        try:
            tags = json.loads(chunk.tags_json or "[]")
        except json.JSONDecodeError:
            tags = []
        chunks.append(
            ChunkOut(
                id=chunk.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                page=chunk.page,
                heading=chunk.heading,
                subject=chunk.subject,
                module=chunk.module,
                knowledge_point_id=chunk.knowledge_point_id,
                knowledge_point_name=chunk.knowledge_point_name,
                tags=tags,
            )
        )
    return MaterialDetail(material=MaterialOut.model_validate(material), chunks=chunks)


@router.post("/materials/{material_id}/reindex", response_model=MaterialOut)
async def reindex(
    material_id: str, db: Annotated[AsyncSession, Depends(get_db)]
) -> MaterialOut:
    try:
        material = await reindex_material(db, material_id)
    except ParseError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return MaterialOut.model_validate(material)


@router.delete("/materials/{material_id}")
async def remove_material(
    material_id: str, db: Annotated[AsyncSession, Depends(get_db)]
) -> dict:
    deleted = await delete_material(db, material_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="资料不存在。")
    return {"ok": True}


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(
    job_id: str, db: Annotated[AsyncSession, Depends(get_db)]
) -> JobOut:
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在。")
    return JobOut.model_validate(job)


@router.post("/search", response_model=SearchResponse)
async def search(
    payload: SearchRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> SearchResponse:
    llm = await load_llm_settings(db)
    embedder = get_embedding_service(llm)
    data = await search_knowledge(
        db,
        payload.query,
        embedder,
        top_k=payload.top_k,
        subject=payload.subject,
        module=payload.module,
    )
    return SearchResponse(
        query=payload.query,
        results=[SearchHit(**hit) for hit in data["chunks"]],
        cards=[KnowledgeCardHit(**card) for card in data["cards"]],
    )
