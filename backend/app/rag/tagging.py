"""Hybrid multi-label tagging and chunk-type classification."""

import json
import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeCard, KnowledgePoint
from app.rag.embeddings import cosine_similarity


@dataclass
class TagLabel:
    knowledge_point_id: str
    knowledge_point_name: str
    subject: str
    module: str
    score: float
    confidence: float
    tags: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "knowledge_point_id": self.knowledge_point_id,
            "knowledge_point_name": self.knowledge_point_name,
            "subject": self.subject,
            "module": self.module,
            "score": round(self.score, 3),
            "confidence": round(self.confidence, 3),
            "tags": self.tags,
        }


@dataclass
class TagResult:
    subject: str = ""
    module: str = ""
    knowledge_point_id: str = ""
    knowledge_point_name: str = ""
    tags: list[str] = field(default_factory=list)
    labels: list[TagLabel] = field(default_factory=list)
    chunk_type: str = "summary"

    def labels_json(self) -> str:
        return json.dumps(
            [label.as_dict() for label in self.labels], ensure_ascii=False
        )


@dataclass
class PreparedPoint:
    point: KnowledgePoint
    keywords: list[str]
    profile: str = ""


_TRAP_RE = re.compile(r"易错|陷阱|误区|注意[：:]|不要|警惕")
_DEFINITION_RE = re.compile(r"是指|定义|含义|称为|指的是")
_METHOD_RE = re.compile(
    r"步骤|方法|技巧|口诀|第一步"
    r"|先[^。]{0,30}再"
    r"|先[^。]{0,30}(看|判断|找|求|算|回|做)"
    r"|再[^。]{0,20}(看|做|回|比较|辨析|搭建|写|列|算)"
)
_FORMULA_RE = re.compile(
    r"(增长率|基期|现期|比重|平均数|增长量|倍数)\s*[=＝]"
    r"|[=＝][^。]{0,30}[÷/×*]"
)
_EXAMPLE_RE = re.compile(r"例题|例如|例[：:1-9]|【例")
_QUESTION_RE = re.compile(
    r"（\s*）|下列[^。]{0,30}(是|为)|请选择|题干|^\s*[ABCD][．.、]"
)
_HEADING_TYPE_HINTS = (
    ("陷阱", "trap"),
    ("易错", "trap"),
    ("公式", "formula"),
    ("特征数字", "formula"),
    ("方法", "method"),
    ("技巧", "method"),
    ("步骤", "method"),
    ("定义", "definition"),
    ("概念", "definition"),
    ("例题", "example"),
    ("范例", "example"),
)


def classify_chunk(text: str, heading: str = "") -> str:
    combined = f"{heading}\n{text}"
    for cue, chunk_type in _HEADING_TYPE_HINTS:
        if cue in heading:
            return chunk_type
    if text.strip().startswith(("例题", "例：", "例1", "【例", "例如")):
        return "example"
    if _QUESTION_RE.search(combined):
        return "question"
    if _TRAP_RE.search(combined):
        return "trap"
    if _DEFINITION_RE.search(combined):
        return "definition"
    if _METHOD_RE.search(combined):
        return "method"
    if _FORMULA_RE.search(combined):
        return "formula"
    if _EXAMPLE_RE.search(combined):
        return "example"
    return "summary"


async def load_prepared_points(db: AsyncSession) -> list[PreparedPoint]:
    points = (
        await db.execute(select(KnowledgePoint))
    ).scalars().all()
    cards = {
        card.id: card
        for card in (await db.execute(select(KnowledgeCard))).scalars()
    }
    prepared: list[PreparedPoint] = []
    for point in points:
        try:
            keywords = json.loads(point.keywords_json or "[]")
        except json.JSONDecodeError:
            keywords = []
        card = cards.get(point.id)
        profile_parts = [
            point.name,
            point.description,
        ]
        if card is not None:
            profile_parts.extend(
                [card.summary, card.methods, card.traps]
            )
        prepared.append(
            PreparedPoint(
                point=point,
                keywords=[
                    str(keyword)
                    for keyword in keywords
                    if str(keyword).strip()
                ],
                profile=" ".join(
                    part.strip() for part in profile_parts if part.strip()
                ),
            )
        )
    return prepared


def _fallback_subject(text: str) -> str:
    if "行测" in text or "行政职业能力" in text:
        return "行测"
    if "申论" in text:
        return "申论"
    return ""


def tag_text_multi(
    text: str,
    prepared: list[PreparedPoint],
    *,
    heading: str = "",
    embedding: list[float] | None = None,
    point_embeddings: dict[str, list[float]] | None = None,
    top_k: int = 3,
) -> TagResult:
    candidates: list[TagLabel] = []
    vectors = point_embeddings or {}
    search_text = f"{heading}\n{text}" if heading else text

    for item in prepared:
        point = item.point
        keyword_score = 0
        matches: list[str] = []
        if point.name and len(point.name) >= 2 and point.name in search_text:
            keyword_score += len(point.name)
            matches.append(point.name)
        for keyword in item.keywords:
            if keyword and keyword in search_text:
                keyword_score += len(keyword)
                matches.append(keyword)

        semantic = 0.0
        vector = vectors.get(point.id)
        if embedding and vector and len(embedding) == len(vector):
            semantic = max(0.0, cosine_similarity(embedding, vector))

        if keyword_score == 0 and semantic < 0.30:
            continue

        keyword_norm = min(keyword_score / 12.0, 1.0)
        score = (
            0.72 * keyword_norm + 0.28 * semantic
            if keyword_score
            else 0.28 * semantic
        )
        if score <= 0:
            continue
        candidates.append(
            TagLabel(
                knowledge_point_id=point.id,
                knowledge_point_name=point.name,
                subject=point.subject,
                module=point.module,
                score=score,
                confidence=min(score, 1.0),
                tags=sorted(set(matches)),
            )
        )

    candidates.sort(key=lambda item: item.score, reverse=True)
    labels = candidates[:top_k]
    chunk_type = classify_chunk(text, heading)

    if not labels:
        return TagResult(
            subject=_fallback_subject(search_text),
            chunk_type=chunk_type,
        )

    primary = labels[0]
    return TagResult(
        subject=primary.subject,
        module=primary.module,
        knowledge_point_id=primary.knowledge_point_id,
        knowledge_point_name=primary.knowledge_point_name,
        tags=primary.tags,
        labels=labels,
        chunk_type=chunk_type,
    )


def tag_text(
    text: str,
    prepared: list[PreparedPoint],
    *,
    heading: str = "",
) -> TagResult:
    """Keyword-only compatibility wrapper."""
    return tag_text_multi(text, prepared, heading=heading)
