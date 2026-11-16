"""Rule-based knowledge-point tagging for the seeded taxonomy."""

import json
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgePoint


@dataclass
class TagResult:
    subject: str = ""
    module: str = ""
    knowledge_point_id: str = ""
    knowledge_point_name: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class PreparedPoint:
    point: KnowledgePoint
    keywords: list[str]


async def load_prepared_points(db: AsyncSession) -> list[PreparedPoint]:
    result = await db.execute(select(KnowledgePoint))
    prepared: list[PreparedPoint] = []
    for point in result.scalars():
        try:
            keywords = json.loads(point.keywords_json or "[]")
        except json.JSONDecodeError:
            keywords = []
        prepared.append(
            PreparedPoint(
                point=point,
                keywords=[str(keyword) for keyword in keywords if str(keyword).strip()],
            )
        )
    return prepared


def tag_text(text: str, prepared: list[PreparedPoint]) -> TagResult:
    best_score = 0
    best: PreparedPoint | None = None
    best_matches: list[str] = []

    for item in prepared:
        score = 0
        matches: list[str] = []
        name = item.point.name
        if name and name in text:
            score += len(name)
            matches.append(name)
        for keyword in item.keywords:
            if keyword in text:
                score += len(keyword)
                matches.append(keyword)
        if score:
            score += item.point.level
        if score > best_score:
            best_score = score
            best = item
            best_matches = matches

    if best is not None:
        return TagResult(
            subject=best.point.subject,
            module=best.point.module,
            knowledge_point_id=best.point.id,
            knowledge_point_name=best.point.name,
            tags=sorted(set(best_matches)),
        )

    subject = ""
    if "行测" in text or "行政职业能力" in text:
        subject = "行测"
    elif "申论" in text:
        subject = "申论"
    return TagResult(subject=subject)
