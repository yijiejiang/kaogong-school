"""Tools for the collector, organizer and knowledge agents."""

import os

import httpx
from google.adk.tools import ToolContext
from sqlalchemy import select

from app.config import get_settings
from app.db.models import Material
from app.db.session import SessionLocal
from app.rag.embeddings import get_embedding_service
from app.rag.index import (
    get_knowledge_card as fetch_knowledge_card,
)
from app.rag.index import (
    list_knowledge_tree as fetch_knowledge_tree,
)
from app.rag.index import (
    search_knowledge as search_index,
)
from app.rag.parsers import ParseError, UnsafeUrl
from app.services.ingestion import create_url_material
from app.services.ingestion import reindex_material as reindex_service
from app.services.settings_service import load_llm_settings


def _material_brief(material: Material) -> dict:
    return {
        "id": material.id,
        "material_id": material.id,
        "title": material.title,
        "kind": material.kind,
        "status": material.status,
        "subject": material.subject,
        "module": material.module,
        "chunk_count": material.chunk_count,
        "error": material.error,
        "source_url": material.source_url,
    }


def _citations(chunks: list[dict]) -> list[str]:
    citations: list[str] = []
    for hit in chunks:
        title = hit.get("material_title") or "资料"
        page = hit.get("page")
        citations.append(f"《{title}》" + (f"第 {page} 页" if page else ""))
    return citations


async def _run_search(
    query: str, subject: str, module: str, top_k: int
) -> dict:
    async with SessionLocal() as db:
        llm = await load_llm_settings(db)
        embedder = get_embedding_service(llm)
        data = await search_index(
            db,
            query,
            embedder,
            top_k=top_k,
            subject=subject,
            module=module,
        )
    chunks = data["chunks"]
    return {
        "status": "success",
        "query": query,
        "cards": data["cards"],
        "chunks": chunks,
        "citations": _citations(chunks),
        "message": (
            f"找到 {len(chunks)} 条相关资料。"
            if chunks
            else "资料库还没有找到相关内容。"
        ),
    }


async def list_materials(tool_context: ToolContext) -> dict:
    """List the most recent materials and their ingestion status.

    Returns titles, status, subject, module, chunk counts and errors. Use it
    before telling the student whether a file is ready.
    """
    async with SessionLocal() as db:
        result = await db.execute(
            select(Material).order_by(Material.created_at.desc()).limit(10)
        )
        materials = [_material_brief(material) for material in result.scalars()]
    return {
        "status": "success",
        "materials": materials,
        "count": len(materials),
        "message": "下面是最近的资料与入库状态。",
    }


async def search_knowledge(
    query: str,
    subject: str,
    module: str,
    tool_context: ToolContext,
) -> dict:
    """Search the knowledge base and return matching cards and source chunks.

    Args:
        query: The student's question or search phrase.
        subject: "行测", "申论", or an empty string when unknown.
        module: A module name such as "资料分析", or an empty string.

    Returns cards, chunks and citation strings. Only answer from this result.
    """
    return await _run_search(query, subject, module, top_k=8)


async def search_materials(query: str, tool_context: ToolContext) -> dict:
    """Search indexed material chunks without the knowledge-card layer.

    Args:
        query: What to look for in the uploaded materials.

    Returns matching chunks and citation strings.
    """
    return await _run_search(query, "", "", top_k=8)


async def get_knowledge_card(kp_id: str, tool_context: ToolContext) -> dict:
    """Read one knowledge card and its source chunks.

    Args:
        kp_id: Stable knowledge-point id, for example "xingce-ziliao-susuan".

    Returns the card summary, methods, traps and up to three source chunks.
    """
    async with SessionLocal() as db:
        data = await fetch_knowledge_card(db, kp_id)
    if data is None:
        return {"status": "not_found", "message": f"没有找到知识点 {kp_id}。"}
    return {"status": "success", "card": data}


async def list_knowledge_tree(tool_context: ToolContext) -> dict:
    """Return the built-in 行测/申论 knowledge tree with chunk counts."""
    async with SessionLocal() as db:
        nodes = await fetch_knowledge_tree(db)
    return {"status": "success", "nodes": nodes, "count": len(nodes)}


async def import_url(url: str, tool_context: ToolContext) -> dict:
    """Register a public web page for ingestion.

    Args:
        url: A public http/https URL. Localhost and private networks are rejected.

    Returns the material status and a UI material card payload.
    """
    async with SessionLocal() as db:
        try:
            material = await create_url_material(db, url)
        except (ParseError, UnsafeUrl) as exc:
            return {"status": "error", "message": str(exc)}
        brief = _material_brief(material)
    return {
        "status": "success",
        "material": brief,
        "message": "已提交入库任务，稍后可在资料库查看进度。",
        "ui": {"type": "material_card", **brief},
    }


async def reindex_material(material_id: str, tool_context: ToolContext) -> dict:
    """Re-run parsing, chunking and embedding for one material.

    Args:
        material_id: The material id shown by list_materials or the library page.
    """
    async with SessionLocal() as db:
        try:
            material = await reindex_service(db, material_id)
        except ParseError as exc:
            return {"status": "error", "message": str(exc)}
        brief = _material_brief(material)
    return {
        "status": "success",
        "material": brief,
        "message": "已重新提交索引，稍后查看状态。",
    }


async def web_search(query: str, tool_context: ToolContext) -> dict:
    """Search the public web with Tavily when TAVILY_API_KEY is configured.

    Args:
        query: Search keywords.

    Returns titles, URLs and snippets. If no key is configured, return a
    clear unavailable message instead of inventing results.
    """
    api_key = get_settings().tavily_api_key.strip() or os.getenv(
        "TAVILY_API_KEY", ""
    ).strip()
    if not api_key:
        return {
            "status": "unavailable",
            "message": "未配置 TAVILY_API_KEY，暂时不能进行网页搜索；可以先上传资料或导入网页链接。",
        }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "max_results": 5,
                    "search_depth": "basic",
                },
            )
            response.raise_for_status()
            data = response.json()
    except Exception as exc:  # noqa: BLE001 - report search failure to the agent
        return {"status": "error", "message": f"网页搜索失败：{exc}"}

    results = [
        {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "content": item.get("content", ""),
        }
        for item in (data.get("results") or [])[:5]
    ]
    return {
        "status": "success",
        "results": results,
        "message": f"找到 {len(results)} 条网页结果。",
    }
