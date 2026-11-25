"""Import huasheng13 skill files into the skill table.

Source: https://github.com/WangJunqing-coder/huasheng13-skill

Usage:
    uv run python scripts/import_huasheng_skills.py --source /path/to/huasheng13-skill
    uv run python scripts/import_huasheng_skills.py --source ... --replace
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import delete, select

from app.db.models import Skill
from app.db.session import SessionLocal

# 文件 → (科目, 模块, 知识点 id, 知识点名)
FILE_META: dict[str, tuple[str, str, str, str]] = {
    "ziliao-fenxi": ("行测", "资料分析", "xingce-ziliao", "资料分析"),
    "ziliao-susuan": ("行测", "资料分析", "xingce-ziliao-susuan", "速算技巧"),
    "ziliao-zonghe": ("行测", "资料分析", "xingce-ziliao", "资料分析"),
    "shuliang-guanxi": ("行测", "数量关系", "xingce-shuliang-yunsuan", "数学运算"),
    "shuliang-gongshi": ("行测", "数量关系", "xingce-shuliang-yunsuan", "数学运算"),
    "yanyu-lianjie": ("行测", "言语理解与表达", "xingce-yanyu", "言语理解与表达"),
    "yanyu-zhuanxiang": ("行测", "言语理解与表达", "xingce-yanyu", "言语理解与表达"),
    "yanyu-ciyu": ("行测", "言语理解与表达", "xingce-yanyu-luoji", "逻辑填空"),
    "panduan-tuili": ("行测", "判断推理", "xingce-panduan", "判断推理"),
    "panduan-tuxing": ("行测", "判断推理", "xingce-panduan-tuxing", "图形推理"),
    "panduan-guilv": ("行测", "判断推理", "xingce-panduan", "判断推理"),
    "changshi-panduan": ("行测", "常识判断", "xingce-changshi", "常识判断"),
    "shizheng-redian": ("行测", "常识判断", "xingce-changshi-zhengzhi", "政治常识"),
    "shenlun": ("申论", "申论", "shenlun", "申论"),
    "shenlun-biaoda": ("申论", "申论", "shenlun-zuowen", "文章写作"),
    "shenlun-sucai": ("申论", "申论", "shenlun-zuowen", "文章写作"),
    "strategy": ("行测", "答题策略", "", ""),
    "cuoti-muban": ("行测", "答题策略", "", ""),
    "beikao-jihua": ("行测", "备考规划", "", ""),
    "zhenti-shili": ("行测", "真题实战", "", ""),
}

SKIP_FILES = {"zhenti-shili"}  # 纯真题，不拆成技能

# 这些标题脱离上下文没有意义，需要拼上父级
GENERIC_TITLES = {
    "解题步骤",
    "二级辨析",
    "总体策略",
    "蒙题技巧",
    "方法介绍",
    "常见题型",
    "高频考点",
    "易错点汇总",
    "真题示例",
    "提速训练路径",
    "配套速记口诀",
}

SECTION_RE = re.compile(r"^(#{2,3})\s+(.+)$")
# 「题型 1：工程问题」「方法 1：截位直除法」「1.2.1 位置规律」「一、ABRX 四要素体系」
NAMED_RE = re.compile(
    r"^(?:题型|方法|技巧|规律|示例)\s*\d+\s*[：:]\s*(.+)$"
)
DECIMAL_RE = re.compile(r"^\d+(?:\.\d+)+\s*(.+)$")
CN_RE = re.compile(r"^[一二三四五六七八九十]+\s*[、.．]\s*(.+)$")

TOPIC_RE = re.compile(r"\*\*识别\*\*\s*[：:]\s*(.+)")
METHOD_BULLET_RE = re.compile(r"^[-*]\s+(.+)$")
TRAP_RE = re.compile(r"^[-*]\s*(?:易错|注意|陷阱)[：:]\s*(.+)$")


@dataclass
class ParsedSection:
    title: str
    level: int
    body: str
    parent: str = ""


def _clean_title(value: str) -> str:
    value = value.strip()
    value = re.sub(r"[*`]", "", value)
    return value.strip(" ：:。#")


def _section_title(raw: str, level: int) -> str | None:
    title = _clean_title(raw)
    if not title:
        return None
    for pattern in (NAMED_RE, DECIMAL_RE, CN_RE):
        match = pattern.match(title)
        if match:
            return _clean_title(match.group(1))
    if level >= 3:
        return title
    return None


def parse_sections(text: str) -> list[ParsedSection]:
    lines = text.splitlines()
    sections: list[ParsedSection] = []
    current: ParsedSection | None = None
    buffer: list[str] = []
    # 记录每个层级最近的标题，用于补全泛化标题
    stack: dict[int, str] = {}

    def flush() -> None:
        nonlocal current, buffer
        if current is not None:
            current.body = "\n".join(buffer).strip()
            sections.append(current)
        buffer = []

    for line in lines:
        match = SECTION_RE.match(line)
        if not match:
            if current is not None:
                buffer.append(line)
            continue
        level = len(match.group(1))
        title = _section_title(match.group(2), level)
        if title is None:
            if current is not None:
                buffer.append(line)
            continue
        flush()
        parent = ""
        for parent_level in sorted(stack, reverse=True):
            if parent_level < level:
                parent = stack[parent_level]
                break
        for key in [k for k in stack if k >= level]:
            del stack[key]
        stack[level] = title
        current = ParsedSection(title=title, level=level, body="", parent=parent)
    flush()
    return sections


def _bullets(body: str, limit: int = 6) -> list[str]:
    items: list[str] = []
    for line in body.splitlines():
        match = METHOD_BULLET_RE.match(line.strip())
        if not match:
            continue
        value = _clean_title(match.group(1))
        # 跳过纯数字、表格式残片
        if len(value) < 4 or not re.search(r"[一-鿿]", value):
            continue
        if value not in items:
            items.append(value[:200])
        if len(items) >= limit:
            break
    return items


def _paragraph_summary(body: str, limit: int = 220) -> str:
    for line in body.splitlines():
        value = line.strip()
        if not value or value.startswith(("#", "|", "-", "*", ">", "```")):
            continue
        value = _clean_title(value)
        if len(value) >= 8:
            return value[:limit]
    return ""


def _signal(body: str) -> list[str]:
    match = TOPIC_RE.search(body)
    if not match:
        return []
    raw = _clean_title(match.group(1))
    parts = re.split(r"[、，,；;]", raw)
    return [item.strip().strip("“”\"'") for item in parts if 2 <= len(item.strip()) <= 30][:5]


def _traps(body: str, limit: int = 4) -> list[str]:
    found: list[str] = []
    for line in body.splitlines():
        match = TRAP_RE.match(line.strip())
        if match:
            value = _clean_title(match.group(1))
            if value and value not in found:
                found.append(value[:200])
        if len(found) >= limit:
            break
    # 兜底：取「易错点」小节里的条目
    if not found and "易错" in body:
        found = _bullets(body.split("易错")[-1], limit)
    return found


def build_skills(source: Path) -> list[dict]:
    skills: list[dict] = []
    refs = source / "references"
    if not refs.is_dir():
        raise SystemExit(f"找不到 {refs}，请用 --source 指向 huasheng13-skill 仓库根目录")

    for path in sorted(refs.glob("*.md")):
        stem = path.stem
        if stem in SKIP_FILES:
            continue
        subject, module, kp_id, kp_name = FILE_META.get(
            stem, ("行测", "其他", "", "")
        )
        text = path.read_text(encoding="utf-8")
        sections = parse_sections(text)

        seen: set[str] = set()
        for section in sections:
            title = section.title
            if len(title) < 2 or len(title) > 60:
                continue
            if title in seen:
                continue
            body = section.body
            if len(body) < 40:
                continue
            seen.add(title)

            summary = _paragraph_summary(body)
            steps = _bullets(body)
            signals = _signal(body)
            traps = _traps(body)

            # 表格残片：摘要里出现连续空白分隔的数字即丢弃
            if re.search(r"\d\s{2,}\d", summary):
                summary = ""
                if not steps and not signals:
                    continue

            # 泛化标题补上父级，例如「解题步骤」→「定义判断·解题步骤」
            if title in GENERIC_TITLES and section.parent:
                title = f"{section.parent}·{title}"

            # 至少要有可执行内容：步骤或识别信号或像样的摘要
            if len(steps) < 2 and not signals and len(summary) < 25:
                continue

            skills.append(
                {
                    "name": title,
                    "subject": subject,
                    "module": module,
                    "knowledge_point_id": kp_id,
                    "knowledge_point_name": kp_name,
                    "summary": summary,
                    "steps": steps,
                    "signals": signals,
                    "pitfalls": traps,
                    "source": f"huasheng13:{path.name}",
                }
            )
    return skills


def _skill_id(item: dict) -> str:
    key = f"{item['source']}|{item['module']}|{item['name']}"
    digest = hashlib.sha1(key.encode()).hexdigest()[:16]
    return f"skill-hs13-{digest}"


async def import_skills(items: list[dict], replace: bool) -> tuple[int, int]:
    async with SessionLocal() as db:
        if replace:
            await db.execute(delete(Skill))
            await db.commit()

        existing = {
            row.id: row
            for row in (
                await db.execute(select(Skill).where(Skill.id.like("skill-hs13-%")))
            ).scalars()
        }
        created = 0
        updated = 0
        for item in items:
            skill_id = _skill_id(item)
            row = existing.get(skill_id)
            if row is None:
                row = Skill(
                    id=skill_id,
                    normalized_name=(
                        f"hs13:{item['source'].split(':')[-1]}|"
                        f"{item['module']}|{item['name']}"
                    )[:128],
                    status="approved",
                )
                db.add(row)
                created += 1
            else:
                updated += 1
            row.name = item["name"][:128]
            row.subject = item["subject"]
            row.module = item["module"][:64]
            row.knowledge_point_id = item["knowledge_point_id"]
            row.knowledge_point_name = item["knowledge_point_name"]
            row.summary = item["summary"]
            row.conditions_json = "[]"
            row.steps_json = json.dumps(item["steps"], ensure_ascii=False)
            row.pitfalls_json = json.dumps(item["pitfalls"], ensure_ascii=False)
            row.examples_json = "[]"
            row.exam_patterns_json = json.dumps(
                [item["source"]], ensure_ascii=False
            )
            row.signals_json = json.dumps(item["signals"], ensure_ascii=False)
            row.variants_json = "[]"
            row.connections_json = "[]"
            row.question_design_json = "[]"
            row.difficulty = 3
            row.source_unit_ids_json = "[]"
            row.confidence = 0.9
            row.source = "huasheng13"
            row.source_ref = item["source"]
            row.status = "approved"
        await db.commit()
    return created, updated


async def main() -> None:
    parser = argparse.ArgumentParser(description="导入花生十三技能到技能表")
    parser.add_argument("--source", required=True, help="huasheng13-skill 仓库路径")
    parser.add_argument(
        "--replace", action="store_true", help="先清空现有技能再导入"
    )
    parser.add_argument("--dry-run", action="store_true", help="只统计不写库")
    args = parser.parse_args()

    items = build_skills(Path(args.source))
    by_module: dict[str, int] = {}
    for item in items:
        by_module[item["module"]] = by_module.get(item["module"], 0) + 1
    print(f"解析出 {len(items)} 条技能：")
    for module, count in sorted(by_module.items(), key=lambda x: -x[1]):
        print(f"  {module}: {count}")

    if args.dry_run:
        for item in items[:10]:
            print("  -", item["module"], "|", item["name"])
        return

    created, updated = await import_skills(items, args.replace)
    print(f"写入完成：新增 {created}，更新 {updated}")


if __name__ == "__main__":
    asyncio.run(main())
