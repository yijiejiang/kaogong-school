"""从解析篇资料补全题库里缺失的答案。

题本篇与解析篇是两份独立 OCR 的 PDF，题号在解析篇里并不可靠，所以按题干原文
对齐：解析篇里「题干 + 四个选项 + 【参考答案】X」是一段连续文本，题库题目的
题干开头必须原样出现在同一段里，才认为答案可靠。

只认带「【参考答案】」标记的题。有些题答案只写在解析末尾（「综上，答案为 X」），
但解析篇的 OCR 会把不同题的段落交错拼在一起，这类题无从确认归属，一律不填。

用法：
    uv run python scripts/backfill_answers.py <题本 material_id> <解析 material_id>
    uv run python scripts/backfill_answers.py --dry-run ...
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Question
from app.db.session import engine

ANS_MARK = re.compile(r"【参考答案】\s*([A-DＡ-Ｄ])")
TYPE_MARK = re.compile(r"【题型分类】\s*([^\n【]{1,60})")
INLINE_OPT = re.compile(r"(?:^|\s)([A-D])\s*[.．、:：]\s*")
NUM_START = re.compile(r"^\s*(\d{1,3})\s*[.．、]", re.MULTILINE)
PLACEHOLDER = re.compile(r"\$\^\{[^}]*\}")
PAREN_TAG = re.compile(r"（[^）]{0,40}）|\([^)]{0,40}\)")
NOISE = re.compile(r"[\s　]+|[“”\"'，。、；：？！,.;:?!【】]")


@dataclass
class AnswerRecord:
    stem: str
    answer: str
    kind: str
    number: int


def normalize(text: str) -> str:
    text = PLACEHOLDER.sub("", text)
    text = PAREN_TAG.sub("", text)
    text = NUM_START.sub("", text, count=1)
    return NOISE.sub("", text)


def _has_full_options(segment: str) -> bool:
    keys = [m.group(1) for m in INLINE_OPT.finditer(segment)]
    for i in range(len(keys)):
        if keys[i : i + 4] == list("ABCD"):
            return True
    return False


def _stem_before_options(segment: str) -> str:
    opts = [(m.start(), m.group(1)) for m in INLINE_OPT.finditer(segment)]
    for i in range(len(opts)):
        if [k for _, k in opts[i : i + 4]] == list("ABCD"):
            return segment[: opts[i][0]]
    return segment


def parse_answers(text: str) -> list[AnswerRecord]:
    """解析篇 → 答案记录。

    以「【参考答案】」为唯一锚点。锚点之前、上一个锚点之后的那一段应是
    本题的题干与选项；要求这段里真的有 A/B/C/D 四个选项，否则说明 OCR 把
    题目切碎了，放弃这一条，避免把答案挂到别的题上。
    """
    records: list[AnswerRecord] = []
    boundary = 0
    for match in re.finditer(r"【参考答案】", text):
        pos = match.start()
        segment = text[boundary:pos]
        boundary = pos

        if not _has_full_options(segment):
            continue
        letter_match = ANS_MARK.match(text[pos:])
        letter = letter_match.group(1) if letter_match else ""
        if not letter:
            continue

        numbers = list(NUM_START.finditer(segment))
        records.append(
            AnswerRecord(
                stem=_stem_before_options(segment),
                answer=letter.translate(str.maketrans("ＡＢＣＤ", "ABCD")),
                kind="answer",
                number=int(numbers[-1].group(1)) if numbers else 0,
            )
        )
    return records


def match(
    questions: list[Question], records: list[AnswerRecord]
) -> tuple[list[tuple[Question, AnswerRecord]], list[Question]]:
    """题干开头原样命中，且只能命中一条。宁可漏，不可错。"""
    normalized = [normalize(record.stem) for record in records]
    matched: list[tuple[Question, AnswerRecord]] = []
    missed: list[Question] = []
    for question in questions:
        head = normalize(question.stem)[:45]
        if len(head) < 20:
            missed.append(question)
            continue
        hits = [i for i, text in enumerate(normalized) if head in text]
        if len(hits) != 1:
            missed.append(question)
            continue
        matched.append((question, records[hits[0]]))
    return matched, missed


async def run(paper_id: str, answer_id: str, dry_run: bool) -> None:
    async with AsyncSession(engine) as db:
        questions = list(
            (
                await db.execute(
                    select(Question).where(
                        Question.material_id == paper_id,
                        Question.answer_json == "{}",
                    )
                )
            ).scalars()
        )
        chunks = list(
            (
                await db.execute(
                    select(Chunk.content)
                    .where(Chunk.material_id == answer_id)
                    .order_by(Chunk.chunk_index)
                )
            ).scalars()
        )
        records = parse_answers("\n".join(chunks))
        matched, missed = match(questions, records)

        print(f"待补答案：{len(questions)} 道；解析篇可靠记录：{len(records)} 条")
        print(f"对齐成功：{len(matched)} 道；未对齐：{len(missed)} 道")
        for question, record in matched[:5]:
            print(f"  {record.answer} ← {question.stem[:40]}")

        if dry_run:
            return
        for question, record in matched:
            question.answer_json = json.dumps({"value": record.answer})
        await db.commit()
        print(f"已写入 {len(matched)} 条答案。")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paper_id", help="题本篇的 material_id")
    parser.add_argument("answer_id", help="解析篇的 material_id")
    parser.add_argument("--dry-run", action="store_true", help="只报告，不写库")
    args = parser.parse_args()
    asyncio.run(run(args.paper_id, args.answer_id, args.dry_run))


if __name__ == "__main__":
    main()
