"""Structured knowledge-unit and skill extraction from indexed chunks."""

import hashlib
import json
import logging
import re
import uuid

import litellm
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Chunk, KnowledgePoint, KnowledgeUnit, Material, Skill
from app.rag.evidence import check_evidence
from app.schemas.settings import LlmSettings
from app.services.extract_scopes import build_scopes, scope_chunk_ids
from app.services.llm import normalize_model, role_model_config
from app.services.usage import record_usage

logger = logging.getLogger(__name__)

ELIGIBLE_TYPES = {"method", "formula", "definition", "trap", "example"}
MAX_RULE_CHUNKS = 30
MAX_LLM_CHUNKS = 4
MAX_UNITS_PER_CHUNK = 2
LLM_MAX_TOKENS = 12000

_PAGE_PREFIX_RE = re.compile(r"^第\s*\d+\s*页\s*")
_WATERMARK_RE = re.compile(r"关注.{0,20}公众号")
_NOISE_LINE_RE = re.compile(r"^(第\s*\d+\s*页|[-—\s]*\d{1,3}[-—\s]*)$")


class ExtractionError(RuntimeError):
    pass


def _clean_title(value: str) -> str:
    value = _PAGE_PREFIX_RE.sub("", (value or "").strip())
    value = re.sub(r"^[#\s]*", "", value)
    value = re.sub(r"^[一二三四五六七八九十百]+[、.．]\s*", "", value)
    value = re.sub(r"^\d+(\.\d+)+[、.．]?\s*", "", value)
    value = value.strip(" ：:.-—")
    if len(value) < 2 or not re.search(r"[一-鿿A-Za-z]", value):
        return ""
    if re.fullmatch(r"[【\[（(]?[例练题答案解析]{1,3}[】\]）)]?", value):
        return ""
    return value[:80]


def _first_line(text: str) -> str:
    for line in text.splitlines():
        value = _PAGE_PREFIX_RE.sub("", line.strip())
        if not value or _NOISE_LINE_RE.match(value):
            continue
        if _WATERMARK_RE.search(value):
            continue
        if not re.search(r"[一-鿿]", value):
            continue
        return value
    return ""


def _heading_title(chunk: Chunk) -> str:
    candidates = [chunk.heading]
    if chunk.heading_path:
        candidates.extend(reversed(chunk.heading_path.split(">")))
    for candidate in candidates:
        title = _clean_title(candidate)
        if title:
            return title
    return ""


def _sentences(text: str) -> list[str]:
    return [
        item.strip()
        for item in re.split(r"[。！？；\n]+", text)
        if item.strip()
    ]


def _pick(sentences: list[str], cues: tuple[str, ...], limit: int = 5) -> list[str]:
    picked = [
        sentence
        for sentence in sentences
        if any(cue in sentence for cue in cues)
    ]
    return picked[:limit]


def _normalize_skill(name: str) -> str:
    value = re.sub(r"[\s，。；、：:（）()【】\[\]·,.;!?！？]+", "", name or "")
    return value.lower()[:80]


def _as_list(value: object, limit: int = 6) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip()[:300] for item in value if str(item).strip()][:limit]
    if isinstance(value, str) and value.strip():
        return [value.strip()[:300]]
    return []


def _as_connections(value: object, limit: int = 4) -> list[dict]:
    if not isinstance(value, list):
        return []
    result: list[dict] = []
    for item in value:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()[:128]
            if not name:
                continue
            result.append(
                {
                    "name": name,
                    "relation": str(item.get("relation") or "关联").strip()[:32],
                    "knowledge_point_id": str(
                        item.get("knowledge_point_id") or ""
                    ).strip()[:64],
                }
            )
        elif str(item).strip():
            result.append(
                {
                    "name": str(item).strip()[:128],
                    "relation": "关联",
                    "knowledge_point_id": "",
                }
            )
        if len(result) >= limit:
            break
    return result


def _clamp(value: object, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, number))


def _rule_unit(chunk: Chunk, model: str = "rule") -> dict | None:
    text = chunk.content
    if len(text.strip()) < 60:
        return None
    sentences = _sentences(text)
    title = _heading_title(chunk) or _clean_title(_first_line(text))[:60]
    if not title:
        informative = [
            sentence
            for sentence in sentences
            if len(sentence) >= 8 and re.search(r"[一-鿿]", sentence)
        ]
        title = _clean_title(informative[0]) if informative else ""
    if not title:
        return None
    summary_text = "\n".join(
        line
        for line in text.splitlines()
        if not _WATERMARK_RE.search(line) and not _NOISE_LINE_RE.match(line.strip())
    )
    summary = summary_text.strip()[:240]
    skill_name = ""
    if chunk.chunk_type in {"method", "formula", "trap"}:
        skill_name = title
    definition = text[:600].strip() if chunk.chunk_type == "definition" else ""
    steps = _pick(
        sentences,
        ("先", "再", "然后", "最后", "步骤", "第一步", "第二步"),
    )
    pitfalls = _pick(
        sentences,
        ("易错", "陷阱", "误区", "注意", "不要", "警惕"),
        4,
    )
    conditions = _pick(
        sentences,
        ("适用", "适合", "条件", "前提", "用于"),
        4,
    )
    examples = _pick(sentences, ("例", "比如", "例如"), 4)
    confidence = 0.55 if chunk.chunk_type != "example" else 0.45
    return {
        "chunk_id": chunk.id,
        "chunk_type": chunk.chunk_type,
        "title": title,
        "summary": summary,
        "definition": definition,
        "conditions": conditions,
        "steps": steps,
        "pitfalls": pitfalls,
        "examples": examples,
        "exam_pattern": "",
        "signals": [],
        "variants": [],
        "question_design": [],
        "connections": [],
        "knowledge_point_id": chunk.knowledge_point_id,
        "knowledge_point_name": chunk.knowledge_point_name,
        "skill_name": skill_name,
        "proposed_knowledge_point": "",
        "proposed_parent_id": "",
        "proposed_reason": "",
        "confidence": confidence,
        "evidence": [
            {"page": chunk.page, "quote": text[:160]}
        ],
        "model": model,
    }


def _parse_units(text: str) -> list[dict]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    candidates: list[str] = []
    for index, char in enumerate(cleaned):
        if char != "{":
            continue
        depth = 0
        in_string = False
        escaped = False
        for position in range(index, len(cleaned)):
            current = cleaned[position]
            if in_string:
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == '"':
                    in_string = False
                continue
            if current == '"':
                in_string = True
            elif current == "{":
                depth += 1
            elif current == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(cleaned[index : position + 1])
                    break
    for candidate in candidates:
        for attempt in (candidate, re.sub(r",\s*([}\]])", r"\1", candidate)):
            try:
                payload = json.loads(attempt, strict=False)
            except json.JSONDecodeError:
                continue
            units = payload.get("units") if isinstance(payload, dict) else None
            if isinstance(units, list):
                return [unit for unit in units if isinstance(unit, dict)]
    return []


def _build_prompt(
    chunks: list[Chunk],
    points: list[KnowledgePoint],
) -> str:
    kp_lines = "\n".join(
        f"- {point.id}：{point.name}" for point in points
    )
    chunk_lines = []
    for index, chunk in enumerate(chunks):
        content = chunk.content[:1400]
        chunk_lines.append(
            f"[{index}] 标题：{chunk.heading or '无'}\n"
            f"类型：{chunk.chunk_type}；当前知识点："
            f"{chunk.knowledge_point_name or '无'}\n{content}"
        )
    return (
        "你是公务员考试教研知识工程师。请从下面的资料片段中抽取可复用的知识单元。\n"
        "每个单元必须能独立用于复习或出题，不要把整段照抄成 summary。\n"
        "只返回 JSON，不要 Markdown：\n"
        '{"units":[{"chunk_index":0,"title":"...","summary":"...",'
        '"definition":"...","conditions":["..."],"steps":["..."],'
        '"pitfalls":["..."],"examples":["..."],'
        '"exam_pattern":"...","signals":["..."],"variants":["..."],'
        '"question_design":["..."],"connections":[{"name":"...",'
        '"relation":"前置/关联/易混","knowledge_point_id":"..."}],'
        '"knowledge_point_id":"...","skill_name":"...","confidence":0.8,'
        '"new_knowledge_point":{"name":"","parent_knowledge_point_id":"",'
        '"reason":""}}]}\n'
        "要求：\n"
        "1. 每个片段最多 2 个单元，没有可复用内容可返回空数组。\n"
        "2. knowledge_point_id 只能从下面选择；不确定就填当前知识点 id。\n"
        f"{kp_lines}\n"
        "3. skill_name 是可复用的技能名，例如“截位直除”“化同法”“增长率变形”。\n"
        "4. steps 写成可执行步骤；pitfalls 写易错点；examples 可引用原文数字。\n"
        "5. exam_pattern 写“这类知识怎么被考”，一两句话。\n"
        "6. signals 写题干中能触发该技能的关键词/结构；variants 写常见变式。\n"
        "7. question_design 写出题人可能怎么设置干扰项或陷阱。\n"
        "8. connections 写与其它知识点/技能的关系，最多 4 条。\n"
        "9. 只有出现现有知识点没覆盖的新考点时，才填写 new_knowledge_point；"
        "name 要具体，parent_knowledge_point_id 从上面列表选，reason 说明为什么是新考点；"
        "否则 name 留空。\n"
        "10. confidence 为 0–1。\n"
        "11. evidence 必填：给出这条知识的可核对出处，格式"
        '{"page": 页码整数, "quote": "原文中连续的 10-40 字"}\n'
        "    页码必须来自上面片段标注的页码；quote 必须能在那一页原文里找到。\n"
        "    如果是你根据资料推导、原文没有直接写的，evidence 填 "
        '{"page": 0, "quote": ""} 并在 summary 里说明是推导。\n'
        "请直接输出最终 JSON，不要输出思考过程。\n\n"
        "资料片段：\n" + "\n\n".join(chunk_lines)
    )


def _normalize_llm_unit(
    raw: dict,
    chunk: Chunk,
    points_by_id: dict[str, KnowledgePoint],
    points_by_name: dict[str, KnowledgePoint],
    model: str,
) -> dict | None:
    title = str(raw.get("title") or "").strip()[:120]
    summary = str(raw.get("summary") or "").strip()[:1000]
    if not title and not summary:
        return None
    kp_id = str(raw.get("knowledge_point_id") or "").strip()
    point = points_by_id.get(kp_id) or points_by_name.get(
        str(raw.get("knowledge_point_name") or "").strip()
    )
    if point is None and chunk.knowledge_point_id:
        point = points_by_id.get(chunk.knowledge_point_id)
    kp_id = point.id if point else chunk.knowledge_point_id
    kp_name = point.name if point else chunk.knowledge_point_name
    proposal = (
        raw.get("new_knowledge_point")
        if isinstance(raw.get("new_knowledge_point"), dict)
        else {}
    )
    proposed_name = str(proposal.get("name") or "").strip()[:128]
    proposed_parent = str(
        proposal.get("parent_knowledge_point_id") or ""
    ).strip()
    if proposed_parent not in points_by_id:
        proposed_parent = kp_id
    return {
        "chunk_id": chunk.id,
        "chunk_type": chunk.chunk_type,
        "title": title or _heading_title(chunk) or "知识单元",
        "summary": summary or chunk.content[:240],
        "definition": str(raw.get("definition") or "").strip()[:1200],
        "conditions": _as_list(raw.get("conditions")),
        "steps": _as_list(raw.get("steps")),
        "pitfalls": _as_list(raw.get("pitfalls")),
        "examples": _as_list(raw.get("examples")),
        "exam_pattern": str(raw.get("exam_pattern") or "").strip()[:600],
        "signals": _as_list(raw.get("signals")),
        "variants": _as_list(raw.get("variants")),
        "question_design": _as_list(raw.get("question_design")),
        "connections": _as_connections(raw.get("connections")),
        "knowledge_point_id": kp_id,
        "knowledge_point_name": kp_name,
        "skill_name": str(raw.get("skill_name") or "").strip()[:80],
        "confidence": _clamp(raw.get("confidence"), 0.7),
        "proposed_knowledge_point": proposed_name,
        "proposed_parent_id": proposed_parent if proposed_name else "",
        "proposed_reason": (
            str(proposal.get("reason") or "").strip()[:300]
            if proposed_name
            else ""
        ),
        "evidence": [{"page": chunk.page, "quote": chunk.content[:160]}],
        "model": model,
    }


async def _llm_units(
    db: AsyncSession,
    chunks: list[Chunk],
    llm: LlmSettings,
    all_page_text: dict[int, str] | None = None,
) -> list[dict]:
    if get_settings().mock_llm:
        raise ExtractionError("mock mode")
    endpoint = role_model_config(llm, "knowledge")
    if not endpoint.model:
        raise ExtractionError("knowledge model not configured")

    points = list((await db.execute(select(KnowledgePoint))).scalars())
    points_by_id = {point.id: point for point in points}
    points_by_name = {point.name: point for point in points}
    kwargs: dict = {
        "model": normalize_model(endpoint.model),
        "messages": [
            {
                "role": "system",
                "content": "你是严谨的考公教研知识工程师，只输出 JSON。",
            },
            {
                "role": "user",
                "content": _build_prompt(chunks, points),
            },
        ],
        "temperature": min(endpoint.temperature, 0.3),
        "max_tokens": max(endpoint.max_tokens or 0, LLM_MAX_TOKENS),
        "timeout": 180,
        "response_format": {"type": "json_object"},
    }
    if endpoint.api_base:
        kwargs["api_base"] = endpoint.api_base
    if endpoint.api_key:
        kwargs["api_key"] = endpoint.api_key

    response = await litellm.acompletion(**kwargs)
    try:
        usage = getattr(response, "usage", None)
        if usage is not None:
            await record_usage(
                db,
                user_id=get_settings().default_user_id,
                session_id="",
                role="knowledge",
                model=endpoint.model,
                prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
                completion_tokens=int(
                    getattr(usage, "completion_tokens", 0) or 0
                ),
                llm=llm,
                api_base=endpoint.api_base,
            )
    except Exception:
        logger.warning("failed to record extraction usage", exc_info=True)
    choice = response.choices[0]
    if getattr(choice, "finish_reason", "") == "length":
        raise ExtractionError("LLM output truncated by token limit")
    text = str(choice.message.content or "")
    raw_units = _parse_units(text)

    # 出处核对用的页文本：优先用整份资料的，拿不到才退回本批
    page_text: dict[int, str] = dict(all_page_text or {})
    if not page_text:
        for chunk in chunks:
            if not chunk.page:
                continue
            page_text[chunk.page] = (
                page_text.get(chunk.page, "") + "\n" + chunk.content
            )

    units: list[dict] = []
    for raw in raw_units:
        try:
            index = int(raw.get("chunk_index"))
        except (TypeError, ValueError):
            continue
        if index < 0 or index >= len(chunks):
            continue
        unit = _normalize_llm_unit(
            raw,
            chunks[index],
            points_by_id,
            points_by_name,
            endpoint.model,
        )
        if unit is None:
            continue
        # 核对出处：页码要在本批范围内，短句要真能在该页找到。
        # 页码在整份资料范围内即可。一页常跨多个块，批边界切在页中间时
        # 引用会落在本批之外，用批次范围会把正确的引用误判掉。
        verdict = check_evidence(
            raw.get("evidence"),
            page_text,
            allowed_pages=set(page_text) if page_text else None,
        )
        unit["evidence_ok"] = verdict.ok
        unit["evidence_reason"] = verdict.reason
        units.append(unit)
    if not units:
        raise ExtractionError("LLM returned no valid units")
    return units


async def _llm_units_batched(
    db: AsyncSession,
    chunks: list[Chunk],
    llm: LlmSettings,
) -> tuple[list[dict], list[str]]:
    units: list[dict] = []
    errors: list[str] = []

    # 整份资料的页文本，供出处核对（一页可能跨多个批次的块）
    all_page_text: dict[int, str] = {}
    for chunk in chunks:
        if not chunk.page:
            continue
        all_page_text[chunk.page] = (
            all_page_text.get(chunk.page, "") + "\n" + chunk.content
        )

    async def run(batch: list[Chunk]) -> None:
        try:
            units.extend(await _llm_units(db, batch, llm, all_page_text))
            return
        except Exception as exc:  # noqa: BLE001 - split and retry
            if len(batch) > 1:
                middle = len(batch) // 2
                await run(batch[:middle])
                await run(batch[middle:])
                return
            logger.warning("knowledge extraction chunk failed: %s", exc)
            errors.append(str(exc)[:120])

    for start in range(0, len(chunks), MAX_LLM_CHUNKS):
        await run(chunks[start : start + MAX_LLM_CHUNKS])
    if not units:
        raise ExtractionError(
            "all batches failed: " + (errors[0] if errors else "no units")
        )
    return units, errors


async def _upsert_skills(
    db: AsyncSession,
    units: list[KnowledgeUnit],
) -> int:
    grouped: dict[str, list[KnowledgeUnit]] = {}
    for unit in units:
        if not unit.skill_id:
            continue
        normalized = unit.skill_id
        grouped.setdefault(normalized, []).append(unit)

    point_rows = list((await db.execute(select(KnowledgePoint))).scalars())
    points = {point.id: point for point in point_rows}
    existing_rows = list((await db.execute(select(Skill))).scalars())
    existing = {skill.normalized_name: skill for skill in existing_rows}
    live_unit_ids = {
        row
        for row in (
            await db.execute(select(KnowledgeUnit.id))
        ).scalars()
    }
    changed = 0

    for normalized, items in grouped.items():
        first = items[0]
        skill = existing.get(normalized)
        if skill is None:
            skill = Skill(
                id=f"skill-{hashlib.sha1(normalized.encode()).hexdigest()[:16]}",
                normalized_name=normalized,
                status="draft",
            )
            db.add(skill)
            existing[normalized] = skill
            changed += 1
        point = points.get(first.knowledge_point_id)
        skill.name = skill.name or first.skill_name or first.title
        skill.subject = point.subject if point else ""
        skill.module = point.module if point else ""
        skill.knowledge_point_id = first.knowledge_point_id
        skill.knowledge_point_name = first.knowledge_point_name
        skill.summary = skill.summary or first.summary
        skill.confidence = max(
            [skill.confidence or 0.0]
            + [item.confidence for item in items]
        )
        skill.steps_json = json.dumps(
            _merge([json.loads(item.steps_json or "[]") for item in items])
        )
        skill.pitfalls_json = json.dumps(
            _merge([json.loads(item.pitfalls_json or "[]") for item in items])
        )
        skill.examples_json = json.dumps(
            _merge([json.loads(item.examples_json or "[]") for item in items])
        )
        skill.conditions_json = json.dumps(
            _merge([json.loads(item.conditions_json or "[]") for item in items])
        )
        skill.exam_patterns_json = json.dumps(
            _merge(
                [
                    [item.exam_pattern]
                    if item.exam_pattern.strip()
                    else []
                    for item in items
                ]
            )
        )
        skill.signals_json = json.dumps(
            _merge([json.loads(item.signals_json or "[]") for item in items])
        )
        skill.variants_json = json.dumps(
            _merge([json.loads(item.variants_json or "[]") for item in items])
        )
        skill.question_design_json = json.dumps(
            _merge(
                [json.loads(item.question_design_json or "[]") for item in items]
            )
        )
        skill.connections_json = json.dumps(
            _merge_connections(
                [
                    json.loads(item.connections_json or "[]")
                    for item in items
                ]
            )
        )
        source_ids = [
            unit_id
            for unit_id in json.loads(skill.source_unit_ids_json or "[]")
            if unit_id in live_unit_ids
        ]
        for item in items:
            if item.id not in source_ids:
                source_ids.append(item.id)
        skill.source_unit_ids_json = json.dumps(source_ids[-50:])
    return changed


def _merge(values: list[list[str]]) -> list[str]:
    merged: list[str] = []
    for items in values:
        for item in items:
            if item and item not in merged:
                merged.append(item)
    return merged[:8]


def _merge_connections(values: list[list[dict]]) -> list[dict]:
    merged: list[dict] = []
    seen: set[str] = set()
    for items in values:
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            merged.append(
                {
                    "name": name,
                    "relation": str(item.get("relation") or "关联"),
                    "knowledge_point_id": str(
                        item.get("knowledge_point_id") or ""
                    ),
                }
            )
    return merged[:6]


async def _prune_skills(db: AsyncSession) -> int:
    unit_ids = {
        row
        for row in (
            await db.execute(select(KnowledgeUnit.id))
        ).scalars()
    }
    rows = list((await db.execute(select(Skill))).scalars())
    removed = 0
    for skill in rows:
        try:
            source_ids = json.loads(skill.source_unit_ids_json or "[]")
        except json.JSONDecodeError:
            source_ids = []
        if skill.status != "draft":
            continue
        if not set(source_ids) & unit_ids:
            await db.delete(skill)
            removed += 1
    return removed


async def extract_material_units(
    db: AsyncSession,
    material_id: str,
    llm: LlmSettings,
) -> dict:
    await db.execute(
        delete(KnowledgeUnit).where(KnowledgeUnit.material_id == material_id)
    )
    # 按范围覆盖全书：原来只取前 30 个「合格类型」的块，长资料后半段
    # 根本抽不到知识；而且 summary 类的讲义正文被排除在外。
    material = await db.get(Material, material_id)
    if material is not None:
        scope_rows = await build_scopes(db, material, kind="knowledge")
    else:
        scope_rows = []
    if scope_rows:
        ids: list[str] = []
        for scope in sorted(scope_rows, key=lambda r: r.order_index):
            for cid in scope_chunk_ids(scope):
                if cid not in ids:
                    ids.append(cid)
        chunks = list(
            (
                await db.execute(
                    select(Chunk)
                    .where(Chunk.id.in_(ids))
                    .order_by(Chunk.chunk_index)
                )
            ).scalars()
        )
    else:
        chunks = list(
            (
                await db.execute(
                    select(Chunk)
                    .where(Chunk.material_id == material_id)
                    .order_by(Chunk.chunk_index)
                    .limit(MAX_RULE_CHUNKS)
                )
            ).scalars()
        )
    if not chunks:
        await db.commit()
        return {
            "units": 0,
            "skills": 0,
            "new_skills": 0,
            "proposals": 0,
            "model": "",
            "warning": "",
        }

    model_name = role_model_config(llm, "knowledge").model
    warning = ""
    units_raw: list[dict] = []
    if get_settings().mock_llm or not model_name:
        model_used = "rule"
    else:
        try:
            units_raw, errors = await _llm_units_batched(
                db, chunks, llm
            )
            model_used = model_name
            if errors:
                warning = (
                    f"部分片段 LLM 抽取失败，已用规则补齐：{errors[0]}"
                )
        except Exception as exc:  # noqa: BLE001 - fallback to deterministic units
            warning = f"LLM 知识抽取回退到规则抽取：{str(exc)[:180]}"
            logger.warning("knowledge extraction fallback: %s", exc)
            model_used = "rule"

    covered = {unit["chunk_id"] for unit in units_raw}
    for chunk in chunks:
        if chunk.id in covered:
            continue
        rule_unit = _rule_unit(chunk, "rule")
        if rule_unit is not None:
            units_raw.append(rule_unit)

    points = list((await db.execute(select(KnowledgePoint))).scalars())
    point_ids = {point.id for point in points}
    known_names = {_normalize_skill(point.name) for point in points}
    proposals = 0
    for raw in units_raw:
        if raw.get("proposed_knowledge_point") or proposals >= 6:
            continue
        parent = raw.get("knowledge_point_id", "")
        candidate = str(raw.get("skill_name") or "").strip()[:128]
        normalized = _normalize_skill(candidate)
        if (
            not candidate
            or parent not in point_ids
            or len(normalized) < 3
            or any(
                normalized in name or name in normalized
                for name in known_names
                if name
            )
        ):
            continue
        raw["proposed_knowledge_point"] = candidate
        raw["proposed_parent_id"] = parent
        raw["proposed_reason"] = "抽取到现有知识树未覆盖的技能/考点。"
        proposals += 1

    unit_rows: list[KnowledgeUnit] = []
    for raw in units_raw[: MAX_RULE_CHUNKS * MAX_UNITS_PER_CHUNK]:
        if not raw.get("title") and not raw.get("summary"):
            continue
        skill_label = str(raw.get("skill_name") or "").strip()[:128]
        normalized_skill = _normalize_skill(skill_label or raw.get("title", ""))
        skill_key = (
            f"{raw.get('knowledge_point_id')}:{normalized_skill}"
            if normalized_skill
            else ""
        )
        row = KnowledgeUnit(
            id=uuid.uuid4().hex,
            material_id=material_id,
            chunk_id=raw["chunk_id"],
            chunk_type=raw.get("chunk_type", "summary"),
            title=raw.get("title", "")[:255],
            summary=raw.get("summary", ""),
            definition=raw.get("definition", ""),
            conditions_json=json.dumps(raw.get("conditions") or [], ensure_ascii=False),
            steps_json=json.dumps(raw.get("steps") or [], ensure_ascii=False),
            pitfalls_json=json.dumps(raw.get("pitfalls") or [], ensure_ascii=False),
            examples_json=json.dumps(raw.get("examples") or [], ensure_ascii=False),
            exam_pattern=raw.get("exam_pattern", ""),
            signals_json=json.dumps(raw.get("signals") or [], ensure_ascii=False),
            variants_json=json.dumps(raw.get("variants") or [], ensure_ascii=False),
            connections_json=json.dumps(
                raw.get("connections") or [], ensure_ascii=False
            ),
            question_design_json=json.dumps(
                raw.get("question_design") or [], ensure_ascii=False
            ),
            knowledge_point_id=raw.get("knowledge_point_id", ""),
            knowledge_point_name=raw.get("knowledge_point_name", ""),
            skill_name=skill_label,
            skill_id=skill_key,
            proposed_knowledge_point=raw.get("proposed_knowledge_point", ""),
            proposed_parent_id=raw.get("proposed_parent_id", ""),
            proposed_reason=raw.get("proposed_reason", ""),
            confidence=raw.get("confidence", 0.5),
            # 出处核对不上的降为待审，不当作可靠知识
            status="draft" if raw.get("evidence_ok", True) else "needs_review",
            evidence_json=json.dumps(raw.get("evidence") or [], ensure_ascii=False),
            evidence_note=str(raw.get("evidence_reason") or "")[:200],
            extraction_model=raw.get("model", model_used),
        )
        db.add(row)
        unit_rows.append(row)

    await db.flush()
    changed_skills = await _upsert_skills(db, unit_rows)
    await _prune_skills(db)
    await db.commit()
    return {
        "units": len(unit_rows),
        "skills": len({row.skill_id for row in unit_rows if row.skill_id}),
        "new_skills": changed_skills,
        "proposals": len(
            {
                row.proposed_knowledge_point
                for row in unit_rows
                if row.proposed_knowledge_point
            }
        ),
        "model": model_used,
        "warning": warning,
    }
