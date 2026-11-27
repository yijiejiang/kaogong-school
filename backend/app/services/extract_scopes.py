"""把一份资料切成互不重叠的抽取范围。

长资料整份塞给模型会超上下文，只取前面若干块又会漏掉后半段。这里按
章节优先、页段兜底的方式切分：每个范围自己能塞进模型，且合起来覆盖全书。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, ExtractScope, Material

# 单个范围的目标字数。留足余量给提示词和输出。
SCOPE_CHARS = 12000
# 极端情况下的保护，避免一页数据异常撑爆
MAX_SCOPES = 200
# 少于这个字数的范围并入相邻段——OCR 常把一道题的条件拆成零碎小块，
# 单独成段既抽不出题，又白白多一次调用
MIN_SCOPE_CHARS = 400


@dataclass
class ScopePlan:
    key: str
    title: str
    page_start: int
    page_end: int
    chunk_ids: list[str]


def doc_version_of(material: Material) -> str:
    """资料版本：入库时间变化即视为新版本。"""
    stamp = material.updated_at or material.created_at
    raw = f"{material.id}|{stamp}|{material.chunk_count}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def plan_scopes(chunks: list[Chunk]) -> list[ScopePlan]:
    """按章节切，章节过大再按页段切。返回的顺序即处理顺序。"""
    if not chunks:
        return []

    plans: list[ScopePlan] = []
    sizes: dict[str, int] = {}
    current: list[Chunk] = []
    current_chars = 0
    current_heading = ""

    def flush() -> None:
        nonlocal current, current_chars, current_heading
        if not current:
            return
        pages = [c.page for c in current if c.page]
        title = current[0].heading_path or current[0].heading or "开头"
        plans.append(
            ScopePlan(
                key=f"s{len(plans):03d}",
                title=title[:120],
                page_start=min(pages) if pages else 0,
                page_end=max(pages) if pages else 0,
                chunk_ids=[c.id for c in current],
            )
        )
        sizes[plans[-1].key] = sum(len(c.content or "") for c in current)
        current = []
        current_chars = 0
        current_heading = ""

    for chunk in chunks:
        heading = chunk.heading_path or chunk.heading or ""
        size = len(chunk.content or "")

        # 换了章节且当前段已有内容，就先收一段
        if current and heading and heading != current_heading:
            flush()

        # 单段太长就先收，避免一个范围过大
        if current and current_chars + size > SCOPE_CHARS:
            flush()

        if not current:
            current_heading = heading
        current.append(chunk)
        current_chars += size

        if len(plans) >= MAX_SCOPES:
            break

    flush()
    return _merge_small(plans, sizes)[:MAX_SCOPES]


def _merge_small(
    plans: list[ScopePlan], chars: dict[str, int]
) -> list[ScopePlan]:
    """把过短的范围并进下一段，减少 OCR 碎片造成的空范围。"""
    if not plans:
        return []

    merged: list[ScopePlan] = []
    carry: ScopePlan | None = None
    carry_chars = 0

    for plan in plans:
        size = chars.get(plan.key, 0)
        if carry is not None:
            plan = ScopePlan(
                key=carry.key,
                title=carry.title,
                page_start=min(carry.page_start or plan.page_start,
                               plan.page_start or carry.page_start),
                page_end=max(carry.page_end, plan.page_end),
                chunk_ids=carry.chunk_ids + plan.chunk_ids,
            )
            size += carry_chars
            carry = None
            carry_chars = 0

        # 太短就先存着，和下一段合并
        if size < MIN_SCOPE_CHARS:
            carry = plan
            carry_chars = size
            continue
        merged.append(plan)

    # 末尾剩下的短段并回上一段
    if carry is not None:
        if merged:
            last = merged[-1]
            merged[-1] = ScopePlan(
                key=last.key,
                title=last.title,
                page_start=min(last.page_start or carry.page_start,
                               carry.page_start or last.page_start),
                page_end=max(last.page_end, carry.page_end),
                chunk_ids=last.chunk_ids + carry.chunk_ids,
            )
        else:
            merged.append(carry)

    return [
        ScopePlan(
            key=f"s{index:03d}",
            title=plan.title,
            page_start=plan.page_start,
            page_end=plan.page_end,
            chunk_ids=plan.chunk_ids,
        )
        for index, plan in enumerate(merged)
    ]


async def build_scopes(
    db: AsyncSession,
    material: Material,
    kind: str = "question",
) -> list[ExtractScope]:
    """按当前分块生成范围清单。同一版本重复调用返回已有清单。"""
    version = doc_version_of(material)
    existing = list(
        (
            await db.execute(
                select(ExtractScope)
                .where(
                    ExtractScope.material_id == material.id,
                    ExtractScope.kind == kind,
                    ExtractScope.doc_version == version,
                )
                .order_by(ExtractScope.order_index)
            )
        ).scalars()
    )
    if existing:
        return existing

    # 旧版本的范围清单已经指向被替换掉的分块，先清掉
    stale = list(
        (
            await db.execute(
                select(ExtractScope).where(
                    ExtractScope.material_id == material.id,
                    ExtractScope.kind == kind,
                    ExtractScope.doc_version != version,
                )
            )
        ).scalars()
    )
    for row in stale:
        await db.delete(row)
    if stale:
        await db.flush()

    chunks = list(
        (
            await db.execute(
                select(Chunk)
                .where(Chunk.material_id == material.id)
                .order_by(Chunk.chunk_index)
            )
        ).scalars()
    )
    plans = plan_scopes(chunks)

    rows: list[ExtractScope] = []
    for index, plan in enumerate(plans):
        row = ExtractScope(
            # 带版本号：重建索引后分块换了，旧清单作废，ID 不能复用
            id=f"{material.id[:8]}-{kind}-{version[:8]}-{plan.key}",
            material_id=material.id,
            kind=kind,
            doc_version=version,
            scope_key=plan.key,
            title=plan.title,
            page_start=plan.page_start,
            page_end=plan.page_end,
            order_index=index,
            status="pending",
            result_json=json.dumps({"chunk_ids": plan.chunk_ids}, ensure_ascii=False),
        )
        db.add(row)
        rows.append(row)
    await db.commit()
    return rows


def scope_chunk_ids(scope: ExtractScope) -> list[str]:
    try:
        data = json.loads(scope.result_json or "{}")
    except json.JSONDecodeError:
        return []
    ids = data.get("chunk_ids")
    return [str(item) for item in ids] if isinstance(ids, list) else []
