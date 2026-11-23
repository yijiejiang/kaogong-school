"""Tools for the collector, organizer and knowledge agents."""

import json
import logging
import os

import httpx
from google.adk.tools import ToolContext
from sqlalchemy import select

from app.config import get_settings
from app.db.models import KnowledgeUnit, Mastery, Material, Skill
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
from app.rag.parsers import ParseError, UnsafeUrl, is_public_url
from app.services.deepseek_tools import (
    DeepSeekError,
    fetch_page,
)
from app.services.deepseek_tools import (
    resolve_config as resolve_deepseek,
)
from app.services.deepseek_tools import (
    search as deepseek_search,
)
from app.services.ingestion import create_url_material
from app.services.ingestion import reindex_material as reindex_service
from app.services.settings_service import load_llm_settings
from app.services.usage import record_service_usage

logger = logging.getLogger(__name__)


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


def _cite_time(seconds: float) -> str:
    total = max(0, int(seconds))
    return f"{total // 60:02d}:{total % 60:02d}"


def _citations(chunks: list[dict]) -> list[str]:
    citations: list[str] = []
    for hit in chunks:
        title = hit.get("material_title") or "资料"
        page = hit.get("page")
        start = hit.get("time_start")
        if start is not None:
            suffix = f"{_cite_time(float(start))}"
            end = hit.get("time_end")
            if end is not None:
                suffix += f"–{_cite_time(float(end))}"
            citations.append(f"《{title}》{suffix}")
        else:
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


def _json_list(value: str) -> list:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _skill_payload(skill: Skill) -> dict:
    return {
        "id": skill.id,
        "name": skill.name,
        "subject": skill.subject,
        "module": skill.module,
        "knowledge_point_id": skill.knowledge_point_id,
        "knowledge_point_name": skill.knowledge_point_name,
        "summary": skill.summary,
        "conditions": _json_list(skill.conditions_json),
        "steps": _json_list(skill.steps_json),
        "pitfalls": _json_list(skill.pitfalls_json),
        "exam_patterns": _json_list(skill.exam_patterns_json),
        "signals": _json_list(skill.signals_json),
        "variants": _json_list(skill.variants_json),
        "question_design": _json_list(skill.question_design_json),
        "connections": _json_list(skill.connections_json),
        "difficulty": skill.difficulty,
        "confidence": skill.confidence,
        "status": skill.status,
        "source_unit_count": len(_json_list(skill.source_unit_ids_json)),
    }


async def find_skills(
    query: str = "",
    subject: str = "",
    module: str = "",
    tool_context: ToolContext | None = None,
) -> dict:
    """Find reusable skills by keyword, subject or module.

    Args:
        query: Skill name, method or knowledge point keyword.
        subject: Optional subject filter, e.g. 行测.
        module: Optional module filter, e.g. 资料分析.
    """
    async with SessionLocal() as db:
        rows = list(
            (
                await db.execute(
                    select(Skill)
                    .where(Skill.status != "rejected")
                    .order_by(Skill.module, Skill.name)
                )
            ).scalars()
        )
    keyword = query.strip().lower()
    matched = []
    for skill in rows:
        if subject and skill.subject != subject:
            continue
        if module and skill.module != module:
            continue
        haystack = " ".join(
            [
                skill.name,
                skill.summary,
                skill.knowledge_point_name,
                " ".join(_json_list(skill.signals_json)),
                " ".join(_json_list(skill.exam_patterns_json)),
            ]
        ).lower()
        if keyword and keyword not in haystack:
            continue
        matched.append(_skill_payload(skill))
    return {
        "status": "success",
        "query": query,
        "count": len(matched),
        "skills": matched[:20],
    }


async def list_skill_catalog(
    tool_context: ToolContext | None = None,
) -> dict:
    """List all skill names grouped by module.

    Use this first when you are unsure which skill covers the student's question.
    Returns only names and modules, so it stays small.
    """
    async with SessionLocal() as db:
        rows = list(
            (
                await db.execute(
                    select(Skill)
                    .where(Skill.status != "rejected")
                    .order_by(Skill.module, Skill.name)
                )
            ).scalars()
        )
    groups: dict[str, list[str]] = {}
    for skill in rows:
        groups.setdefault(f"{skill.subject}·{skill.module}", []).append(
            skill.name
        )
    return {
        "status": "success",
        "total": len(rows),
        "modules": [
            {"module": key, "count": len(names), "skills": names}
            for key, names in groups.items()
        ],
    }


async def load_module_skills(
    module: str,
    tool_context: ToolContext | None = None,
) -> dict:
    """Load the full content of every skill in one module.

    Use this when the student asks about a whole module, or when one question
    may involve several skills. Keep the module string short, e.g. 资料分析.

    Args:
        module: Module name, e.g. 资料分析 / 数量关系 / 判断推理.
    """
    module = module.strip()
    if not module:
        return {"status": "error", "message": "请指定模块。"}
    async with SessionLocal() as db:
        rows = list(
            (
                await db.execute(
                    select(Skill)
                    .where(Skill.status != "rejected", Skill.module == module)
                    .order_by(Skill.name)
                )
            ).scalars()
        )
    return {
        "status": "success",
        "module": module,
        "count": len(rows),
        "skills": [_skill_payload(skill) for skill in rows],
    }


async def get_skill_detail(
    skill_id_or_name: str,
    tool_context: ToolContext | None = None,
) -> dict:
    """Read one skill's full detail, steps, exam patterns and source units.

    Args:
        skill_id_or_name: Skill id or skill name shown by find_skills.
    """
    async with SessionLocal() as db:
        skill = await db.get(Skill, skill_id_or_name)
        if skill is None:
            rows = list(
                (
                    await db.execute(
                        select(Skill).where(
                            Skill.name == skill_id_or_name,
                            Skill.status != "rejected",
                        )
                    )
                ).scalars()
            )
            if not rows:
                rows = list(
                    (
                        await db.execute(
                            select(Skill).where(
                                Skill.name.contains(skill_id_or_name),
                                Skill.status != "rejected",
                            )
                        )
                    ).scalars()
                )
            skill = rows[0] if rows else None
        if skill is None:
            return {"status": "not_found", "message": "没有找到对应技能。"}
        source_ids = _json_list(skill.source_unit_ids_json)[-8:]
        units = []
        if source_ids:
            unit_rows = list(
                (
                    await db.execute(
                        select(KnowledgeUnit).where(
                            KnowledgeUnit.id.in_(source_ids)
                        )
                    )
                ).scalars()
            )
            material_ids = {unit.material_id for unit in unit_rows}
            material_rows = list(
                (
                    await db.execute(
                        select(Material).where(Material.id.in_(material_ids))
                    )
                ).scalars()
            )
            materials = {item.id: item.title for item in material_rows}
            units = [
                {
                    "title": unit.title,
                    "summary": unit.summary,
                    "material_title": materials.get(unit.material_id, ""),
                }
                for unit in unit_rows
            ]
    return {
        "status": "success",
        "skill": _skill_payload(skill),
        "source_units": units,
    }


async def get_skill_overview(
    subject: str = "",
    module: str = "",
    tool_context: ToolContext | None = None,
) -> dict:
    """Summarize the student's skill map and list weak skills.

    Args:
        subject: Optional subject filter.
        module: Optional module filter.
    """
    user_id = "local-user"
    if tool_context is not None:
        state = getattr(tool_context, "state", None) or {}
        user_id = str(state.get("user_id") or user_id)
    async with SessionLocal() as db:
        skills = list(
            (
                await db.execute(
                    select(Skill).where(Skill.status != "rejected")
                )
            ).scalars()
        )
        mastery_rows = list(
            (
                await db.execute(
                    select(Mastery).where(Mastery.user_id == user_id)
                )
            ).scalars()
        )
    mastery = {row.knowledge_point_id: row for row in mastery_rows}
    counts = {
        "strong": 0,
        "practicing": 0,
        "learning": 0,
        "unpracticed": 0,
    }
    weak: list[dict] = []
    for skill in skills:
        if subject and skill.subject != subject:
            continue
        if module and skill.module != module:
            continue
        row = mastery.get(skill.knowledge_point_id)
        if row is None or not row.attempts:
            status = "unpracticed"
        elif row.score >= 80:
            status = "strong"
        elif row.score >= 60:
            status = "practicing"
        else:
            status = "learning"
        counts[status] += 1
        if status in {"learning", "unpracticed"}:
            weak.append(
                {
                    "name": skill.name,
                    "module": skill.module,
                    "knowledge_point_name": skill.knowledge_point_name,
                    "status": status,
                    "score": row.score if row else None,
                }
            )
    return {
        "status": "success",
        "user_id": user_id,
        "counts": counts,
        "weak_skills": weak[:12],
    }


async def save_skill(
    name: str,
    module: str,
    summary: str,
    steps: list[str],
    signals: list[str] | None = None,
    pitfalls: list[str] | None = None,
    variants: list[str] | None = None,
    exam_pattern: str = "",
    knowledge_point_id: str = "",
    tool_context: ToolContext | None = None,
) -> dict:
    """Save a reusable skill into the skill map.

    Only call this when the student explicitly asks to save or add a skill.
    Args:
        name: Skill name, short and concrete, e.g. 截位直除法.
        module: Module the skill belongs to, e.g. 资料分析 / 数量关系 / 判断推理.
        summary: One or two sentences on what the skill does.
        steps: Executable steps.
        signals: Keywords that reveal this skill in a question.
        pitfalls: Common mistakes.
        variants: Common variations.
        exam_pattern: How this skill is tested.
        knowledge_point_id: Optional knowledge point id from the tree.
    """
    import hashlib

    from app.db.models import Skill

    module = module.strip()
    name = name.strip()
    if not module or not name:
        return {"status": "error", "message": "技能名称和模块不能为空。"}

    subject = "申论" if module in {"申论"} else "行测"
    key = f"manual|{module}|{name}"
    skill_id = f"skill-manual-{hashlib.sha1(key.encode()).hexdigest()[:16]}"

    async with SessionLocal() as db:
        point = None
        if knowledge_point_id:
            from app.db.models import KnowledgePoint

            point = await db.get(KnowledgePoint, knowledge_point_id)

        row = await db.get(Skill, skill_id)
        if row is None:
            row = Skill(
                id=skill_id,
                normalized_name=key[:128],
                status="approved",
            )
            db.add(row)
        row.name = name[:128]
        row.subject = point.subject if point else subject
        row.module = module[:64]
        row.knowledge_point_id = point.id if point else ""
        row.knowledge_point_name = point.name if point else ""
        row.summary = summary.strip()[:1000]
        row.steps_json = json.dumps(steps or [], ensure_ascii=False)
        row.pitfalls_json = json.dumps(pitfalls or [], ensure_ascii=False)
        row.signals_json = json.dumps(signals or [], ensure_ascii=False)
        row.variants_json = json.dumps(variants or [], ensure_ascii=False)
        row.exam_patterns_json = json.dumps(
            [exam_pattern] if exam_pattern.strip() else [], ensure_ascii=False
        )
        row.confidence = 0.9
        await db.commit()
        await db.refresh(row)
        payload = _skill_payload(row)

    return {
        "status": "success",
        "message": f"已保存技能「{name}」到 {module}。",
        "skill": payload,
    }


async def save_knowledge(
    title: str,
    summary: str,
    steps: list[str] | None = None,
    pitfalls: list[str] | None = None,
    signals: list[str] | None = None,
    exam_pattern: str = "",
    variant: str = "",
    material_id: str = "",
    knowledge_point_id: str = "",
    tool_context: ToolContext | None = None,
) -> dict:
    """Save a deep analysis of one specific question into knowledge mining.

    Use this for a single question analysis, not for a reusable skill.
    Only call it when the student explicitly asks to save the analysis.
    Args:
        title: Short title of this knowledge note.
        summary: The analysis conclusion.
        steps: Solving steps for this question.
        pitfalls: Traps in this question.
        signals: How to recognise this question type.
        exam_pattern: What this question tests.
        variant: One variation of the question.
        material_id: Optional source material id.
        knowledge_point_id: Optional knowledge point id.
    """
    import uuid

    from app.db.models import KnowledgeUnit

    title = title.strip()
    summary = summary.strip()
    if not title or not summary:
        return {"status": "error", "message": "标题和内容不能为空。"}

    point = None
    async with SessionLocal() as db:
        if knowledge_point_id:
            from app.db.models import KnowledgePoint

            point = await db.get(KnowledgePoint, knowledge_point_id)

        row = KnowledgeUnit(
            id=uuid.uuid4().hex,
            material_id=material_id or "",
            chunk_id="",
            chunk_type="question",
            title=title[:255],
            summary=summary,
            definition="",
            conditions_json="[]",
            steps_json=json.dumps(steps or [], ensure_ascii=False),
            pitfalls_json=json.dumps(pitfalls or [], ensure_ascii=False),
            examples_json="[]",
            exam_pattern=exam_pattern.strip(),
            signals_json=json.dumps(signals or [], ensure_ascii=False),
            variants_json=json.dumps(
                [variant] if variant.strip() else [], ensure_ascii=False
            ),
            connections_json="[]",
            question_design_json="[]",
            knowledge_point_id=point.id if point else "",
            knowledge_point_name=point.name if point else "",
            skill_name="",
            skill_id="",
            confidence=0.9,
            status="approved",
            evidence_json="[]",
            extraction_model="manual",
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        unit_id = row.id

    return {
        "status": "success",
        "message": f"已保存知识「{title}」到知识挖掘。",
        "unit_id": unit_id,
    }


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


async def _deepseek_config():
    async with SessionLocal() as db:
        llm = await load_llm_settings(db)
    return resolve_deepseek(llm)


def _current_user(tool_context: ToolContext | None) -> str:
    if tool_context is None:
        return "local-user"
    state = getattr(tool_context, "state", None) or {}
    return str(state.get("user_id") or "local-user")


async def _record_tool_usage(
    service: str,
    units: float,
    user_id: str,
    model: str = "",
) -> None:
    try:
        async with SessionLocal() as db:
            llm = await load_llm_settings(db)
            await record_service_usage(
                db,
                user_id=user_id,
                service=service,
                provider="deepseek",
                units=units,
                llm=llm,
                model=model,
            )
            await db.commit()
    except Exception:
        logger.warning("failed to record %s usage", service, exc_info=True)


async def read_web_page(url: str, tool_context: ToolContext) -> dict:
    """Read one public web page and return its Markdown text.

    Args:
        url: A public http/https URL.
    """
    if not is_public_url(url):
        return {"status": "error", "message": "只允许读取公网 http/https 地址。"}
    config = await _deepseek_config()
    if not config.ready:
        return {
            "status": "unavailable",
            "message": "未配置 DeepSeek API Key，暂时不能抓取网页内容。",
        }
    try:
        page = await fetch_page(config, url)
    except DeepSeekError as exc:
        return {"status": "error", "message": str(exc)}
    await _record_tool_usage("fetch", 1, _current_user(tool_context))
    content = page["content"]
    return {
        "status": "success",
        "title": page["title"],
        "url": url,
        "content": content[:8000],
        "truncated": len(content) > 8000,
    }


async def web_search(query: str, tool_context: ToolContext) -> dict:
    """Search the public web through DeepSeek, then Tavily as a fallback.

    Args:
        query: Search keywords.

    Returns titles, URLs and snippets. If no search provider is configured,
    return a clear unavailable message instead of inventing results.
    """
    deepseek_error = ""
    config = await _deepseek_config()
    if config.ready:
        try:
            results = await deepseek_search(
                config, query, count=5, need_content=True
            )
            if results:
                await _record_tool_usage(
                    "search", 1, _current_user(tool_context)
                )
                return {
                    "status": "success",
                    "provider": "deepseek",
                    "results": [
                        {
                            "title": item["title"],
                            "url": item["url"],
                            "content": (
                                item["summary"]
                                or item["snippet"]
                                or item["content"][:800]
                            ),
                        }
                        for item in results
                    ],
                    "message": f"找到 {len(results)} 条网页结果。",
                }
        except DeepSeekError as exc:
            deepseek_error = str(exc)

    api_key = get_settings().tavily_api_key.strip() or os.getenv(
        "TAVILY_API_KEY", ""
    ).strip()
    if not api_key:
        message = "未配置 DeepSeek API Key 或 TAVILY_API_KEY，暂时不能进行网页搜索；可以先上传资料或导入网页链接。"
        if deepseek_error:
            message = f"DeepSeek 搜索失败（{deepseek_error}），且未配置 Tavily。"
        return {"status": "unavailable", "message": message}

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
        "provider": "tavily",
        "results": results,
        "message": f"找到 {len(results)} 条网页结果。",
    }
