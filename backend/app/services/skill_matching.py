"""Map questions to reusable skills by knowledge point and text signals."""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Skill


def _json_list(value: str) -> list:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def skill_payload(skill: Skill) -> dict:
    return {
        "id": skill.id,
        "name": skill.name,
        "subject": skill.subject,
        "module": skill.module,
        "knowledge_point_id": skill.knowledge_point_id,
        "knowledge_point_name": skill.knowledge_point_name,
        "summary": skill.summary,
        "exam_patterns": _json_list(skill.exam_patterns_json),
        "signals": _json_list(skill.signals_json),
        "steps": _json_list(skill.steps_json),
        "pitfalls": _json_list(skill.pitfalls_json),
        "variants": _json_list(skill.variants_json),
        "question_design": _json_list(skill.question_design_json),
        "confidence": skill.confidence,
        "status": skill.status,
    }


async def load_skill_index(db: AsyncSession) -> dict[str, list[dict]]:
    rows = list(
        (
            await db.execute(select(Skill).where(Skill.status != "rejected"))
        ).scalars()
    )
    index: dict[str, list[dict]] = {}
    for skill in rows:
        index.setdefault(skill.knowledge_point_id, []).append(
            skill_payload(skill)
        )
    return index


def match_skills(
    text: str,
    knowledge_point_id: str,
    index: dict[str, list[dict]],
    limit: int = 3,
) -> list[dict]:
    candidates = index.get(knowledge_point_id, [])
    if not candidates:
        return []
    scored: list[tuple[int, dict]] = []
    for skill in candidates:
        score = 0
        for token in [skill.get("name", ""), *skill.get("signals", [])]:
            token = str(token).strip()
            if len(token) >= 2 and token in text:
                score += len(token)
        if score:
            scored.append((score, skill))
    scored.sort(key=lambda item: item[0], reverse=True)
    if scored:
        return [skill for _, skill in scored[:limit]]
    return [
        max(
            candidates,
            key=lambda item: float(item.get("confidence") or 0),
        )
    ]
