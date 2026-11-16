from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.rag.index import get_knowledge_card, list_knowledge_tree
from app.schemas.materials import KnowledgeCardOut, KnowledgeNode

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("/tree", response_model=list[KnowledgeNode])
async def knowledge_tree(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[KnowledgeNode]:
    return [KnowledgeNode(**node) for node in await list_knowledge_tree(db)]


@router.get("/cards/{kp_id}", response_model=KnowledgeCardOut)
async def knowledge_card(
    kp_id: str, db: Annotated[AsyncSession, Depends(get_db)]
) -> KnowledgeCardOut:
    data = await get_knowledge_card(db, kp_id)
    if data is None:
        raise HTTPException(status_code=404, detail="知识点不存在。")
    return KnowledgeCardOut(**data)
