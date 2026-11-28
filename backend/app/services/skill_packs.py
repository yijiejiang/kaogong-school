"""Skill pack registry: list installed sources, import from a git repo or a URL."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Skill

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
}

SKIP_FILES = {"zhenti-shili"}

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
NAMED_RE = re.compile(r"^(?:题型|方法|技巧|规律|示例)\s*\d+\s*[：:]\s*(.+)$")
DECIMAL_RE = re.compile(r"^\d+(?:\.\d+)+\s*(.+)$")
CN_RE = re.compile(r"^[一二三四五六七八九十]+\s*[、.．]\s*(.+)$")
TOPIC_RE = re.compile(r"\*\*识别\*\*\s*[：:]\s*(.+)")
BULLET_RE = re.compile(r"^[-*]\s+(.+)$")
TRAP_RE = re.compile(r"^[-*]\s*(?:易错|注意|陷阱)[：:]\s*(.+)")
EXAM_RE = re.compile(r"\*\*(?:怎么考|考查方式|题型特点|常见考法|出题形式)\*\*\s*[：:]\s*(.+)")
CJK_RE = re.compile(r"[一-鿿]")


class SkillPackError(RuntimeError):
    pass


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
    sections: list[ParsedSection] = []
    current: ParsedSection | None = None
    buffer: list[str] = []
    stack: dict[int, str] = {}

    def flush() -> None:
        nonlocal current, buffer
        if current is not None:
            current.body = "\n".join(buffer).strip()
            sections.append(current)
        buffer = []

    for line in text.splitlines():
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
        match = BULLET_RE.match(line.strip())
        if not match:
            continue
        value = _clean_title(match.group(1))
        if len(value) < 4 or not CJK_RE.search(value):
            continue
        if value not in items:
            items.append(value[:200])
        if len(items) >= limit:
            break
    return items


def _summary(body: str, limit: int = 220) -> str:
    for line in body.splitlines():
        value = line.strip()
        if not value or value.startswith(("#", "|", "-", "*", ">", "```")):
            continue
        value = _clean_title(value)
        if len(value) >= 8:
            return value[:limit]
    return ""


def _signals(body: str) -> list[str]:
    match = TOPIC_RE.search(body)
    if not match:
        return []
    raw = _clean_title(match.group(1))
    parts = re.split(r"[、，,；;]", raw)
    return [
        item.strip().strip("“”\"'")
        for item in parts
        if 2 <= len(item.strip()) <= 30
    ][:5]


def _exam_patterns(body: str, limit: int = 3) -> list[str]:
    """提取「怎么考」这类描述。原文没写就返回空，不要拿文件名顶替。"""
    found: list[str] = []
    for match in EXAM_RE.finditer(body):
        value = _clean_title(match.group(1))
        if value and len(value) >= 6 and value not in found:
            found.append(value[:120])
        if len(found) >= limit:
            break
    return found


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
    if not found and "易错" in body:
        found = _bullets(body.split("易错")[-1], limit)
    return found


def build_skills(source: Path) -> list[dict]:
    refs = source / "references"
    if not refs.is_dir():
        raise SkillPackError(
            "仓库里没有 references/ 目录，确认这是 huasheng13-skill 结构。"
        )
    skills: list[dict] = []
    for path in sorted(refs.glob("*.md")):
        stem = path.stem
        if stem in SKIP_FILES:
            continue
        subject, module, kp_id, kp_name = FILE_META.get(
            stem, ("行测", "其他", "", "")
        )
        text = path.read_text(encoding="utf-8")
        seen: set[str] = set()
        for section in parse_sections(text):
            title = section.title
            if len(title) < 2 or len(title) > 60 or title in seen:
                continue
            body = section.body
            if len(body) < 40:
                continue
            seen.add(title)

            summary = _summary(body)
            if re.search(r"\d\s{2,}\d", summary):
                summary = ""
                if not _bullets(body) and not _signals(body):
                    continue
            if title in GENERIC_TITLES and section.parent:
                title = f"{section.parent}·{title}"

            steps = _bullets(body)
            signals = _signals(body)
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
                    "pitfalls": _traps(body),
                    "exam_patterns": _exam_patterns(body),
                    "source_ref": f"{path.name}",
                }
            )
    return skills


def skill_id_for(source: str, item: dict) -> str:
    key = f"{source}|{item['source_ref']}|{item['module']}|{item['name']}"
    return f"skill-{source}-{hashlib.sha1(key.encode()).hexdigest()[:16]}"


async def apply_skills(
    db: AsyncSession,
    source_key: str,
    items: list[dict],
    *,
    replace_source: bool = True,
) -> dict:
    """Write parsed skills for one source, replacing its previous rows."""
    existing = {
        row.id: row
        for row in (
            await db.execute(
                select(Skill).where(Skill.source == source_key)
            )
        ).scalars()
    }
    if replace_source:
        for row in existing.values():
            if row.status != "rejected":
                await db.delete(row)
        await db.flush()
        existing = {}

    created = 0
    kept = 0
    for item in items:
        sid = skill_id_for(source_key, item)
        row = existing.get(sid)
        if row is None:
            row = Skill(
                id=sid,
                normalized_name=(
                    f"{source_key}:{item['source_ref']}|"
                    f"{item['module']}|{item['name']}"
                )[:128],
                status="approved",
            )
            db.add(row)
            created += 1
        else:
            kept += 1
        row.name = item["name"][:128]
        row.subject = item["subject"]
        row.module = item["module"][:64]
        row.knowledge_point_id = item["knowledge_point_id"]
        row.knowledge_point_name = item["knowledge_point_name"]
        row.summary = item["summary"]
        row.steps_json = json.dumps(item["steps"], ensure_ascii=False)
        row.pitfalls_json = json.dumps(item["pitfalls"], ensure_ascii=False)
        row.signals_json = json.dumps(item["signals"], ensure_ascii=False)
        # 这里原来塞的是「来源文件名」，不是考法内容——前端显示成
        # 「怎么考：huasheng13:shizheng-redian.md」这种无意义文本。
        # 解析器没提取到考法就留空，前端按「暂无」处理。
        row.exam_patterns_json = json.dumps(
            item.get("exam_patterns") or [], ensure_ascii=False
        )
        row.source = source_key
        row.source_ref = item["source_ref"]
        row.confidence = 0.9
        row.status = "approved"
    await db.commit()
    return {"created": created, "kept": kept, "total": len(items)}


def clone_repo(url: str, target: Path, timeout: int = 300) -> Path:
    stripped = url.strip()
    if not re.match(r"^(https|git|ssh)://|^git@", stripped):
        raise SkillPackError("只支持 http(s) 或 git 协议的仓库地址。")
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", stripped, str(target)],
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise SkillPackError("本机没有 git，无法拉取技能仓库。") from exc
    except subprocess.TimeoutExpired as exc:
        raise SkillPackError("拉取技能仓库超时。") from exc
    if result.returncode != 0:
        detail = (result.stderr or "").strip()[:300]
        raise SkillPackError(f"拉取失败：{detail}")
    return target


async def import_from_repo(
    db: AsyncSession,
    repo_url: str,
    *,
    source_key: str = "huasheng13",
) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="skillpack-"))
    try:
        clone_repo(repo_url, tmp / "repo")
        items = await asyncio.to_thread(build_skills, tmp / "repo")
        if not items:
            raise SkillPackError("仓库里没有解析出技能，检查目录结构。")
        result = await apply_skills(db, source_key, items)
        return {"source": source_key, "repo": repo_url, **result}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def install_builtin(tmp: Path) -> Path:
    """Copy the bundled skill pack into a temp dir for parsing."""
    # 内置技能包放在 backend/skillpacks/，不放在 data/（data 目录不入库）
    builtin = (
        Path(__file__).resolve().parent.parent.parent
        / "skillpacks"
        / "huasheng13"
    )
    if not builtin.is_dir():
        raise SkillPackError("内置技能包不存在。")
    target = tmp / "repo"
    shutil.copytree(builtin, target)
    return target


async def install_builtin_pack(db: AsyncSession) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="skillpack-"))
    try:
        repo = install_builtin(tmp)
        items = await asyncio.to_thread(build_skills, repo)
        result = await apply_skills(db, "huasheng13", items)
        return {"source": "huasheng13", "repo": "builtin", **result}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


async def list_sources(db: AsyncSession) -> list[dict]:
    rows = list((await db.execute(select(Skill))).scalars())
    grouped: dict[str, dict] = {}
    for row in rows:
        key = row.source or "manual"
        entry = grouped.setdefault(
            key,
            {
                "source": key,
                "count": 0,
                "modules": set(),
                "refs": set(),
                "last_updated": None,
            },
        )
        entry["count"] += 1
        if row.module:
            entry["modules"].add(row.module)
        if row.source_ref:
            entry["refs"].add(row.source_ref)
        stamp = row.updated_at
        if stamp and (entry["last_updated"] is None or stamp > entry["last_updated"]):
            entry["last_updated"] = stamp
    result = []
    for entry in grouped.values():
        result.append(
            {
                "source": entry["source"],
                "label": SOURCE_LABELS.get(entry["source"], entry["source"]),
                "count": entry["count"],
                "modules": sorted(entry["modules"]),
                "file_count": len(entry["refs"]),
                "last_updated": (
                    entry["last_updated"].isoformat()
                    if entry["last_updated"]
                    else None
                ),
            }
        )
    result.sort(key=lambda item: item["count"], reverse=True)
    return result


SOURCE_LABELS = {
    "huasheng13": "花生十三体系",
    "manual": "对话中新增",
    "extraction": "资料自动抽取",
}


def known_packs() -> list[dict]:
    return [
        {
            "key": "huasheng13",
            "label": "花生十三体系",
            "repo": "https://github.com/WangJunqing-coder/huasheng13-skill",
            "description": "行测六大模块 + 申论 + 答题策略 + 备考规划，约 230 项技能。",
            "builtin": True,
        }
    ]
