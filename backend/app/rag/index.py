"""Chunk storage and hybrid retrieval."""

import hashlib
import json
import uuid
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Chunk,
    KnowledgeCard,
    KnowledgePoint,
    KnowledgeUnit,
    Material,
)
from app.rag.embeddings import EmbeddingService, cosine_similarity
from app.rag.tagging import TagResult
from app.rag.text import keyword_score, truncate


@dataclass
class TaggedChunk:
    content: str
    heading: str
    heading_path: str
    page: int | None
    tag: TagResult
    time_start: float | None = None
    time_end: float | None = None
    frame_path: str = ""
    page_image_path: str = ""


async def replace_chunks(
    db: AsyncSession,
    material: Material,
    chunks: list[TaggedChunk],
    embeddings: list[list[float]],
    embedding_name: str,
) -> int:
    await db.execute(delete(Chunk).where(Chunk.material_id == material.id))
    await db.execute(
        delete(KnowledgeUnit).where(KnowledgeUnit.material_id == material.id)
    )

    seen_hashes: set[str] = set()
    inserted = 0
    for chunk, vector in zip(chunks, embeddings, strict=False):
        content_hash = hashlib.sha256(chunk.content.encode("utf-8")).hexdigest()
        if content_hash in seen_hashes:
            continue
        seen_hashes.add(content_hash)
        db.add(
            Chunk(
                id=uuid.uuid4().hex,
                material_id=material.id,
                chunk_index=inserted,
                content=chunk.content,
                content_hash=content_hash,
                embedding_json=json.dumps([round(value, 6) for value in vector]),
                embedding_dim=len(vector),
                embedding_model=embedding_name,
                page=chunk.page,
                time_start=chunk.time_start,
                time_end=chunk.time_end,
                frame_path=chunk.frame_path,
                page_image_path=chunk.page_image_path,
                heading=chunk.heading,
                heading_path=chunk.heading_path,
                chunk_type=chunk.tag.chunk_type,
                subject=chunk.tag.subject,
                module=chunk.tag.module,
                knowledge_point_id=chunk.tag.knowledge_point_id,
                knowledge_point_name=chunk.tag.knowledge_point_name,
                tags_json=json.dumps(chunk.tag.tags, ensure_ascii=False),
                labels_json=chunk.tag.labels_json(),
            )
        )
        inserted += 1

    subjects = Counter(chunk.tag.subject for chunk in chunks if chunk.tag.subject)
    modules = Counter(chunk.tag.module for chunk in chunks if chunk.tag.module)
    material.subject = subjects.most_common(1)[0][0] if subjects else ""
    material.module = modules.most_common(1)[0][0] if modules else ""
    material.chunk_count = inserted
    material.embedding_model = embedding_name
    await db.commit()
    return inserted


def _chunk_hit(chunk: Chunk, material: Material, score: float) -> dict:
    try:
        tags = json.loads(chunk.tags_json or "[]")
    except json.JSONDecodeError:
        tags = []
    try:
        labels = json.loads(chunk.labels_json or "[]")
    except json.JSONDecodeError:
        labels = []
    return {
        "chunk_id": chunk.id,
        "material_id": chunk.material_id,
        "material_title": material.title,
        "page": chunk.page,
        "time_start": chunk.time_start,
        "time_end": chunk.time_end,
        "frame_url": (
            f"/api/materials/{chunk.material_id}/frames/"
            f"{chunk.frame_path.rsplit('/', 1)[-1]}"
            if chunk.frame_path
            else ""
        ),
        "heading": chunk.heading,
        "heading_path": chunk.heading_path,
        "chunk_type": chunk.chunk_type,
        "content": truncate(chunk.content, 500),
        "score": round(score, 4),
        "subject": chunk.subject,
        "module": chunk.module,
        "knowledge_point_id": chunk.knowledge_point_id,
        "knowledge_point_name": chunk.knowledge_point_name,
        "tags": tags,
        "labels": labels,
    }


async def search_chunks(
    db: AsyncSession,
    query: str,
    embedder: EmbeddingService,
    subject: str = "",
    module: str = "",
    top_k: int = 8,
    material_id: str = "",
) -> list[dict]:
    query_vector = (await embedder.embed([query]))[0]
    statement = (
        select(Chunk, Material)
        .join(Material, Chunk.material_id == Material.id)
        .where(Material.status == "ready")
    )
    if subject:
        statement = statement.where(Chunk.subject == subject)
    if module:
        statement = statement.where(Chunk.module == module)
    if material_id:
        statement = statement.where(Chunk.material_id == material_id)

    rows = (await db.execute(statement)).all()
    hits: list[dict] = []
    for chunk, material in rows:
        try:
            vector = json.loads(chunk.embedding_json or "[]")
        except json.JSONDecodeError:
            continue
        if not vector:
            continue
        cosine = cosine_similarity(query_vector, vector)
        keyword = keyword_score(query, f"{chunk.heading}\n{chunk.content}")
        score = 0.65 * max(cosine, 0.0) + 0.35 * keyword
        if score <= 0:
            continue
        hits.append(_chunk_hit(chunk, material, score))

    hits.sort(key=lambda item: item["score"], reverse=True)
    return hits[:top_k]


async def search_knowledge(
    db: AsyncSession,
    query: str,
    embedder: EmbeddingService,
    top_k: int = 5,
    subject: str = "",
    module: str = "",
) -> dict:
    chunks = await search_chunks(
        db,
        query,
        embedder,
        subject=subject,
        module=module,
        top_k=top_k * 2,
    )
    chunk_point_ids: set[str] = set()
    for chunk in chunks:
        if chunk.get("knowledge_point_id"):
            chunk_point_ids.add(chunk["knowledge_point_id"])
        for label in chunk.get("labels") or []:
            label_id = label.get("knowledge_point_id")
            if label_id:
                chunk_point_ids.add(label_id)

    cards_result = await db.execute(select(KnowledgeCard))
    scored_cards: list[tuple[float, KnowledgeCard]] = []
    for card in cards_result.scalars():
        if not card.methods.strip() and not card.traps.strip():
            continue
        text = f"{card.title} {card.summary} {card.methods} {card.traps}"
        score = keyword_score(query, text)
        if card.title and card.title in query:
            score += 1.0
        if card.id in chunk_point_ids:
            score += 0.5
        if score >= 0.25:
            scored_cards.append((score, card))

    scored_cards.sort(key=lambda item: item[0], reverse=True)
    cards = [
        {
            "kp_id": card.id,
            "title": card.title,
            "summary": card.summary,
            "methods": card.methods,
            "traps": card.traps,
        }
        for _, card in scored_cards[:3]
    ]
    return {"cards": cards, "chunks": chunks[:top_k]}


async def get_knowledge_card(db: AsyncSession, kp_id: str) -> dict | None:
    card = await db.get(KnowledgeCard, kp_id)
    if card is None:
        return None

    result = await db.execute(
        select(Chunk, Material)
        .join(Material, Chunk.material_id == Material.id)
        .where(Chunk.knowledge_point_id == kp_id, Material.status == "ready")
        .limit(3)
    )
    chunks = [
        _chunk_hit(chunk, material, 1.0) for chunk, material in result.all()
    ]
    return {
        "kp_id": card.id,
        "title": card.title,
        "summary": card.summary,
        "methods": card.methods,
        "traps": card.traps,
        "source_chunks": chunks,
    }


async def list_knowledge_tree(db: AsyncSession) -> list[dict]:
    points = (
        await db.execute(
            select(KnowledgePoint).order_by(
                KnowledgePoint.sort_order, KnowledgePoint.id
            )
        )
    ).scalars().all()

    counts_result = await db.execute(
        select(Chunk.knowledge_point_id, func.count(Chunk.id))
        .join(Material, Chunk.material_id == Material.id)
        .where(Material.status == "ready")
        .group_by(Chunk.knowledge_point_id)
    )
    direct_counts = dict(counts_result.all())

    children: dict[str, list[str]] = {}
    for point in points:
        if point.parent_id:
            children.setdefault(point.parent_id, []).append(point.id)

    def aggregate(node_id: str) -> int:
        total = direct_counts.get(node_id, 0)
        for child_id in children.get(node_id, []):
            total += aggregate(child_id)
        return total

    tree: list[dict] = []
    for point in points:
        try:
            keywords = json.loads(point.keywords_json or "[]")
        except json.JSONDecodeError:
            keywords = []
        tree.append(
            {
                "id": point.id,
                "parent_id": point.parent_id,
                "name": point.name,
                "subject": point.subject,
                "module": point.module,
                "level": point.level,
                "description": point.description,
                "keywords": keywords,
                "chunk_count": aggregate(point.id),
            }
        )
    return tree
