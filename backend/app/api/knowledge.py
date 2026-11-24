import hashlib
import json
from datetime import UTC, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    KnowledgePoint,
    KnowledgeUnit,
    Material,
    Skill,
    SkillMastery,
    utcnow,
)
from app.db.session import get_db
from app.rag.extraction import extract_material_units
from app.rag.index import get_knowledge_card, list_knowledge_tree
from app.schemas.materials import (
    KnowledgeCardOut,
    KnowledgeNode,
    KnowledgeUnitOut,
    KnowledgeUnitUpdate,
    SkillOut,
    SkillUpdate,
)
from app.services.analytics import load_mastery_items
from app.services.settings_service import load_llm_settings

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

VALID_STATUS = {"draft", "approved", "rejected"}


def _list(value: str) -> list:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _unit_out(unit: KnowledgeUnit) -> KnowledgeUnitOut:
    return KnowledgeUnitOut(
        id=unit.id,
        material_id=unit.material_id,
        chunk_id=unit.chunk_id,
        chunk_type=unit.chunk_type,
        title=unit.title,
        summary=unit.summary,
        definition=unit.definition,
        conditions=_list(unit.conditions_json),
        steps=_list(unit.steps_json),
        pitfalls=_list(unit.pitfalls_json),
        examples=_list(unit.examples_json),
        exam_pattern=unit.exam_pattern,
        signals=_list(unit.signals_json),
        variants=_list(unit.variants_json),
        connections=_list(unit.connections_json),
        question_design=_list(unit.question_design_json),
        knowledge_point_id=unit.knowledge_point_id,
        knowledge_point_name=unit.knowledge_point_name,
        skill_name=unit.skill_name,
        skill_id=unit.skill_id,
        proposed_knowledge_point=unit.proposed_knowledge_point,
        proposed_parent_id=unit.proposed_parent_id,
        proposed_reason=unit.proposed_reason,
        confidence=unit.confidence,
        status=unit.status,
        evidence=_list(unit.evidence_json),
        extraction_model=unit.extraction_model,
        created_at=unit.created_at,
        updated_at=unit.updated_at,
    )


def _skill_out(skill: Skill) -> SkillOut:
    return SkillOut(
        id=skill.id,
        name=skill.name,
        normalized_name=skill.normalized_name,
        subject=skill.subject,
        module=skill.module,
        knowledge_point_id=skill.knowledge_point_id,
        knowledge_point_name=skill.knowledge_point_name,
        summary=skill.summary,
        conditions=_list(skill.conditions_json),
        steps=_list(skill.steps_json),
        pitfalls=_list(skill.pitfalls_json),
        examples=_list(skill.examples_json),
        exam_patterns=_list(skill.exam_patterns_json),
        signals=_list(skill.signals_json),
        variants=_list(skill.variants_json),
        connections=_list(skill.connections_json),
        question_design=_list(skill.question_design_json),
        difficulty=skill.difficulty,
        source_unit_ids=_list(skill.source_unit_ids_json),
        source=skill.source,
        source_ref=skill.source_ref,
        confidence=skill.confidence,
        status=skill.status,
        created_at=skill.created_at,
        updated_at=skill.updated_at,
    )


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


@router.get("/units", response_model=list[KnowledgeUnitOut])
async def knowledge_units(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str = "",
    material_id: str = "",
    knowledge_point_id: str = "",
    has_proposal: bool = False,
    limit: int = 100,
) -> list[KnowledgeUnitOut]:
    statement = select(KnowledgeUnit).order_by(
        KnowledgeUnit.created_at.desc()
    )
    if status:
        statement = statement.where(KnowledgeUnit.status == status)
    if material_id:
        statement = statement.where(KnowledgeUnit.material_id == material_id)
    if knowledge_point_id:
        statement = statement.where(
            KnowledgeUnit.knowledge_point_id == knowledge_point_id
        )
    if has_proposal:
        statement = statement.where(
            KnowledgeUnit.proposed_knowledge_point != ""
        )
    rows = (
        await db.execute(statement.limit(max(1, min(limit, 300))))
    ).scalars()
    return [_unit_out(unit) for unit in rows]


@router.patch("/units/{unit_id}", response_model=KnowledgeUnitOut)
async def update_knowledge_unit(
    unit_id: str,
    payload: KnowledgeUnitUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KnowledgeUnitOut:
    unit = await db.get(KnowledgeUnit, unit_id)
    if unit is None:
        raise HTTPException(status_code=404, detail="知识单元不存在。")

    data = payload.model_dump(exclude_unset=True)
    status = data.pop("status", None)
    if status is not None:
        if status not in VALID_STATUS:
            raise HTTPException(status_code=400, detail="状态不合法。")
        unit.status = status
    for field in ("title", "summary", "definition", "exam_pattern"):
        if field in data and data[field] is not None:
            setattr(unit, field, str(data[field]))
    for field, column in (
        ("conditions", "conditions_json"),
        ("steps", "steps_json"),
        ("pitfalls", "pitfalls_json"),
        ("examples", "examples_json"),
        ("signals", "signals_json"),
        ("variants", "variants_json"),
        ("connections", "connections_json"),
        ("question_design", "question_design_json"),
    ):
        if field in data and data[field] is not None:
            setattr(
                unit,
                column,
                json.dumps(data[field], ensure_ascii=False),
            )
    if "knowledge_point_id" in data and data["knowledge_point_id"] is not None:
        kp_id = str(data["knowledge_point_id"]).strip()
        point = await db.get(KnowledgePoint, kp_id)
        if point is None:
            raise HTTPException(status_code=400, detail="知识点不存在。")
        unit.knowledge_point_id = point.id
        unit.knowledge_point_name = point.name
    elif (
        "knowledge_point_name" in data
        and data["knowledge_point_name"] is not None
    ):
        unit.knowledge_point_name = str(data["knowledge_point_name"])

    await db.commit()
    await db.refresh(unit)
    return _unit_out(unit)


@router.get("/skills", response_model=list[SkillOut])
async def skills(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str = "",
    knowledge_point_id: str = "",
    limit: int = 100,
) -> list[SkillOut]:
    statement = select(Skill).order_by(Skill.updated_at.desc())
    if status:
        statement = statement.where(Skill.status == status)
    if knowledge_point_id:
        statement = statement.where(
            Skill.knowledge_point_id == knowledge_point_id
        )
    rows = (
        await db.execute(statement.limit(max(1, min(limit, 300))))
    ).scalars()
    return [_skill_out(skill) for skill in rows]


@router.patch("/skills/{skill_id}", response_model=SkillOut)
async def update_skill(
    skill_id: str,
    payload: SkillUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SkillOut:
    skill = await db.get(Skill, skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="技能不存在。")
    data = payload.model_dump(exclude_unset=True)
    status = data.pop("status", None)
    if status is not None:
        if status not in VALID_STATUS:
            raise HTTPException(status_code=400, detail="状态不合法。")
        skill.status = status
    if data.get("name") is not None:
        skill.name = str(data["name"])
    if data.get("summary") is not None:
        skill.summary = str(data["summary"])
    await db.commit()
    await db.refresh(skill)
    return _skill_out(skill)


@router.post("/units/{unit_id}/create-point")
async def create_point_from_unit(
    unit_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    unit = await db.get(KnowledgeUnit, unit_id)
    if unit is None:
        raise HTTPException(status_code=404, detail="知识单元不存在。")
    name = (unit.proposed_knowledge_point or unit.title).strip()
    if not name:
        raise HTTPException(status_code=400, detail="没有可创建的知识点名称。")
    name = name[:128]

    existing = (
        await db.execute(
            select(KnowledgePoint).where(KnowledgePoint.name == name)
        )
    ).scalar_one_or_none()
    parent = await db.get(KnowledgePoint, unit.proposed_parent_id) if unit.proposed_parent_id else None
    if existing is None:
        if parent is None:
            raise HTTPException(
                status_code=400,
                detail="找不到建议的父级知识点，请先在知识树中补全。",
            )
        point_id = f"kp-{hashlib.sha1(name.encode()).hexdigest()[:12]}"
        existing = KnowledgePoint(
            id=point_id,
            parent_id=parent.id,
            name=name,
            subject=parent.subject,
            module=parent.module,
            description=unit.proposed_reason or unit.summary[:300],
            keywords_json=json.dumps([name], ensure_ascii=False),
            level=(parent.level or 1) + 1,
            sort_order=1000,
        )
        db.add(existing)
        await db.flush()

    unit.knowledge_point_id = existing.id
    unit.knowledge_point_name = existing.name
    unit.status = "approved"
    unit.proposed_knowledge_point = ""
    unit.proposed_parent_id = ""
    unit.proposed_reason = ""
    await db.commit()
    await db.refresh(unit)
    return {
        "status": "success",
        "knowledge_point": {
            "id": existing.id,
            "name": existing.name,
            "parent_id": existing.parent_id,
            "subject": existing.subject,
            "module": existing.module,
        },
        "unit": _unit_out(unit).model_dump(),
    }


def _skill_units(
    db: AsyncSession,
    skill: Skill,
    units_by_id: dict[str, KnowledgeUnit],
    materials: dict[str, Material],
) -> list[dict]:
    try:
        source_ids = json.loads(skill.source_unit_ids_json or "[]")
    except json.JSONDecodeError:
        source_ids = []
    result: list[dict] = []
    for unit_id in source_ids[-12:]:
        unit = units_by_id.get(unit_id)
        if unit is None:
            continue
        material = materials.get(unit.material_id)
        result.append(
            {
                "id": unit.id,
                "title": unit.title,
                "summary": unit.summary,
                "material_id": unit.material_id,
                "material_title": material.title if material else "",
                "status": unit.status,
            }
        )
    return result


_MASTERY_LABELS = {
    "unpracticed": "不清楚",
    "learning": "了解",
    "practicing": "会用",
    "strong": "熟练",
    "due": "待复习",
}

_MASTERY_ORDER = {
    "due": 0,
    "learning": 1,
    "unpracticed": 2,
    "practicing": 3,
    "strong": 4,
}


def _mastery_label(status: str) -> str:
    return _MASTERY_LABELS.get(status, "不清楚")


def _skill_mastery_state(row: SkillMastery | None) -> dict:
    if row is None or not row.attempts:
        return {
            "status": "unpracticed",
            "score": None,
            "attempts": 0,
            "correct": 0,
            "due_at": None,
        }
    score = float(row.score or 0)
    status = "strong" if score >= 80 else "practicing" if score >= 60 else "learning"
    due_at = None
    if row.last_practiced is not None:
        last = row.last_practiced
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        interval = 1 if score < 40 else 3 if score < 60 else 7 if score < 80 else 14
        due = last + timedelta(days=interval)
        due_at = due.date().isoformat()
        if due <= utcnow():
            status = "due"
    return {
        "status": status,
        "score": round(score, 1),
        "attempts": row.attempts,
        "correct": row.correct,
        "due_at": due_at,
    }


@router.get("/skill-map")
async def skill_map(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: str = "local-user",
) -> dict:
    mastery_items = await load_mastery_items(db, user_id)
    mastery_by_kp = {
        item["knowledge_point_id"]: item for item in mastery_items
    }
    skill_mastery_rows = list(
        (
            await db.execute(
                select(SkillMastery).where(SkillMastery.user_id == user_id)
            )
        ).scalars()
    )
    mastery_by_skill = {
        row.skill_id: row for row in skill_mastery_rows
    }
    skills = list(
        (
            await db.execute(
                select(Skill)
                .where(Skill.status != "rejected")
                .order_by(Skill.module, Skill.name)
            )
        ).scalars()
    )
    unit_rows = list((await db.execute(select(KnowledgeUnit))).scalars())
    units_by_id = {unit.id: unit for unit in unit_rows}

    groups: dict[tuple[str, str], list[dict]] = {}
    summary = {
        "total": 0,
        "strong": 0,
        "practicing": 0,
        "learning": 0,
        "unpracticed": 0,
        "due": 0,
    }
    for skill in skills:
        mastery = mastery_by_kp.get(skill.knowledge_point_id)
        skill_state = _skill_mastery_state(mastery_by_skill.get(skill.id))
        if skill_state["attempts"]:
            status = skill_state["status"]
            score = skill_state["score"]
            attempts = skill_state["attempts"]
            correct = skill_state["correct"]
            due_at = skill_state["due_at"]
            mastery_source = "skill"
        else:
            status = mastery["status"] if mastery else "unpracticed"
            score = mastery.get("decayed_score") if mastery else None
            attempts = mastery["attempts"] if mastery else 0
            correct = mastery["correct"] if mastery else 0
            due_at = mastery.get("due_at") if mastery else None
            mastery_source = "knowledge_point" if attempts else "none"
        try:
            source_ids = json.loads(skill.source_unit_ids_json or "[]")
        except json.JSONDecodeError:
            source_ids = []
        source_materials = {
            units_by_id[unit_id].material_id
            for unit_id in source_ids
            if unit_id in units_by_id
        }
        item = {
            "id": skill.id,
            "name": skill.name,
            "subject": skill.subject,
            "module": skill.module,
            "knowledge_point_id": skill.knowledge_point_id,
            "knowledge_point_name": skill.knowledge_point_name,
            "summary": skill.summary,
            "confidence": skill.confidence,
            "difficulty": skill.difficulty,
            "status": skill.status,
            "mastery_status": status,
            "mastery_label": _mastery_label(status),
            "mastery_source": mastery_source,
            "score": score,
            "attempts": attempts,
            "correct": correct,
            "due_at": due_at,
            "source_unit_count": len(source_ids),
            "source_material_count": len(source_materials),
            "exam_patterns": _list(skill.exam_patterns_json),
            "signals": _list(skill.signals_json),
            "variants": _list(skill.variants_json),
            "question_design": _list(skill.question_design_json),
            "connections": _list(skill.connections_json),
            "steps": _list(skill.steps_json),
            "pitfalls": _list(skill.pitfalls_json),
        }
        groups.setdefault(
            (skill.subject or "未分类", skill.module or "未分类"), []
        ).append(item)
        summary["total"] += 1
        if status in summary:
            summary[status] += 1

    subjects: list[dict] = []
    for (subject, module), items in groups.items():
        module_counts = {
            key: sum(1 for item in items if item["mastery_status"] == key)
            for key in ("strong", "practicing", "learning", "unpracticed", "due")
        }
        scored = [item["score"] for item in items if item["score"] is not None]
        total = len(items)
        # 0–100 健康度：熟练 100、会用 75、了解 50、不清楚 15、待复习 30
        weights = {
            "strong": 100,
            "practicing": 75,
            "learning": 50,
            "unpracticed": 15,
            "due": 30,
        }
        health = round(
            sum(weights[key] * module_counts[key] for key in weights) / total,
            1,
        ) if total else 0.0
        needs_work = (
            module_counts["learning"]
            + module_counts["unpracticed"]
            + module_counts["due"]
        )
        subjects.append(
            {
                "subject": subject,
                "module": module,
                "counts": module_counts,
                "health": health,
                "total": total,
                "needs_work": needs_work,
                "weak_ratio": round(needs_work / total, 3) if total else 0.0,
                "average_score": round(sum(scored) / len(scored), 1)
                if scored
                else None,
                "skills": sorted(
                    items,
                    key=lambda item: (
                        _MASTERY_ORDER.get(item["mastery_status"], 9),
                        item["score"] if item["score"] is not None else 999,
                        item["name"],
                    ),
                ),
            }
        )
    subjects.sort(
        key=lambda item: (item["health"], item["subject"], item["module"])
    )
    weakest = next(
        (
            item
            for item in subjects
            if item["module"] not in {"", "未分类"} and item["needs_work"]
        ),
        None,
    )
    return {
        "user_id": user_id,
        "summary": summary,
        "subjects": subjects,
        "headline": (
            f"{weakest['subject']} · {weakest['module']} 最需要补："
            f"{weakest['needs_work']} 项技能还没练熟"
            if weakest
            else "所有模块的技能都已练习过。"
        ),
    }


@router.get("/skills/{skill_id}")
async def skill_detail(
    skill_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    skill = await db.get(Skill, skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="技能不存在。")
    unit_rows = list((await db.execute(select(KnowledgeUnit))).scalars())
    units_by_id = {unit.id: unit for unit in unit_rows}
    material_rows = list((await db.execute(select(Material))).scalars())
    materials = {material.id: material for material in material_rows}
    return {
        "skill": _skill_out(skill).model_dump(),
        "units": _skill_units(db, skill, units_by_id, materials),
    }


@router.post("/extract/{material_id}")
async def extract_material(
    material_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    material = await db.get(Material, material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="资料不存在。")
    llm = await load_llm_settings(db)
    result = await extract_material_units(db, material_id, llm)
    return {"status": "success", **result}


class SkillPackImportRequest(BaseModel):
    repo: str = ""
    use_builtin: bool = False
    source_key: str = "huasheng13"


@router.get("/skill-sources")
async def skill_sources(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """已安装的技能来源，以及可安装的技能包。"""
    from app.services.skill_packs import known_packs, list_sources

    installed = await list_sources(db)
    packs = known_packs()
    installed_keys = {item["source"] for item in installed}
    for pack in packs:
        pack["installed"] = pack["key"] in installed_keys
    return {"sources": installed, "packs": packs}


@router.post("/skill-sources/import")
async def import_skill_pack(
    payload: SkillPackImportRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """从内置包或 git 仓库导入技能。"""
    from app.services.skill_packs import (
        SkillPackError,
        import_from_repo,
        install_builtin_pack,
    )

    try:
        if payload.use_builtin:
            result = await install_builtin_pack(db)
        elif payload.repo.strip():
            result = await import_from_repo(
                db, payload.repo.strip(), source_key=payload.source_key
            )
        else:
            raise HTTPException(
                status_code=400, detail="请提供仓库地址，或选择内置技能包。"
            )
    except SkillPackError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "success", **result}
