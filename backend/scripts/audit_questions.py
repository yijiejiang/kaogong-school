"""扫描存量资料题，把判不了分的标成待审。

抽取规则改严之前入库的题可能缺答案或答案不在选项里。它们仍在可组卷池里，
一进试卷就会白送分或拉低掌握度。这个脚本先只读统计，确认后再改状态。

用法：
    uv run python scripts/audit_questions.py            # 只看统计
    uv run python scripts/audit_questions.py --apply    # 落实修改
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.db.models import Question
from app.db.session import SessionLocal
from app.services.question_validation import check_question


async def run(apply: bool) -> None:
    async with SessionLocal() as db:
        rows = list(
            (
                await db.execute(
                    select(Question).where(
                        Question.source == "material",
                        Question.quality_status == "approved",
                    )
                )
            ).scalars()
        )
        print(f"待扫描的资料题：{len(rows)} 道")

        reasons: Counter[str] = Counter()
        bad: list[Question] = []
        for row in rows:
            ok, reason = check_question(
                qtype=row.type,
                stem=row.stem,
                options_json=row.options_json,
                answer_json=row.answer_json,
                rubric_json=row.rubric_json,
            )
            if ok:
                continue
            reasons[reason] += 1
            bad.append(row)

        if not bad:
            print("全部合格，无需处理。")
            return

        print(f"不合格：{len(bad)} 道")
        for reason, count in reasons.most_common():
            print(f"  {reason}: {count}")

        if not apply:
            print("\n这是只读扫描。加 --apply 才会把状态改成 needs_review。")
            return

        for row in bad:
            row.quality_status = "needs_review"
        await db.commit()
        print(f"\n已把 {len(bad)} 道题标为 needs_review。")
        print("已有试卷里的题不受影响，历史报告照常可读。")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="真正写入，不加只做统计"
    )
    args = parser.parse_args()
    asyncio.run(run(args.apply))


if __name__ == "__main__":
    main()
