"""Map questions to reusable skills by knowledge point and text signals."""

import json
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Skill

# 这些模块的技能描述的是学习节奏和应试策略，不该拿来匹配具体题干
NON_QUESTION_MODULES = {"备考规划", "答题策略"}


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
        # 知识点 id 体系不一致时会取不到候选：
        # 题目用 shenlun-fenxi，技能里只有 shenlun；还有一批技能 id 是空的。
        # 在同模块范围内按名称/信号词再找一次。
        return _match_across(text, index, limit, _modules_of(index, knowledge_point_id))
    scored: list[tuple[int, dict]] = []
    for skill in candidates:
        score = 0
        for token in [skill.get("name", ""), *skill.get("signals", [])]:
            token = str(token).strip()
            if len(token) >= 2 and token in text:
                score += len(token)
        if score:
            scored.append((score, skill))
    scored.sort(
        key=lambda item: (bool(item[1].get("steps")), item[0]), reverse=True
    )
    if scored:
        return [skill for _, skill in scored[:limit]]

    # 一个信号都没命中时，贸然拿「置信度最高」的那个会给出完全不相关的技能
    # （例如逻辑判断题匹配到图形推理的「样式规律」）。宁可空着，让前端
    # 显示「暂无对应技能」，也不要给出误导性的错配。
    return []


def _match_across(
    text: str,
    index: dict[str, list[dict]],
    limit: int = 3,
    same_modules: set[str] | None = None,
) -> list[dict]:
    """在全部技能里按名称和信号词匹配，要求至少命中一个有意义的词。

    这是知识点 id 对不上时的兜底。宁可给一个来自别的知识点、但名称和题干
    确实相关的技能，也不要因为 id 体系不一致就判成「无技能」。
    """
    scored: list[tuple[int, dict]] = []
    for skills in index.values():
        for skill in skills:
            # 备考规划、答题策略这类是元技能，不对应具体题目，
            # 拿它们去匹配题干只会出现「这题考的是第二个月提升期」这种荒谬结果
            module = str(skill.get("module") or "").strip()
            if module in NON_QUESTION_MODULES:
                continue
            # 只在同模块内跨知识点匹配。跨模块的「增长」「条件」这类
            # 高频词会把牛吃草的技能挂到 GDP 增长率的题上。
            if same_modules and module not in same_modules:
                continue
            score = 0
            for token in [skill.get("name", ""), *skill.get("signals", [])]:
                token = str(token).strip()
                if len(token) < 2:
                    continue
                if token in text:
                    score += len(token)
                    continue
                # 措辞常对不上：技能写「增长了百分之几」，题干写「同比增长率」。
                # 退一步用二元片段覆盖，命中够多也算相关。
                score += _partial_score(token, text)
            if score >= 3:
                scored.append((score, skill))
    # 有步骤的优先：像「加强削弱（3-4 题，重点）」这种只是分类标签，
    # 没有任何可执行步骤，拿它当技能依据讲不出东西来
    scored.sort(
        key=lambda item: (
            bool(item[1].get("steps")),
            item[0],
        ),
        reverse=True,
    )
    if scored:
        return [skill for _, skill in scored[:limit]]
    return _module_fallback(index)


def _module_fallback(index: dict[str, list[dict]]) -> list[dict]:
    """一个都匹配不上时，给出模块级的「总体解题流程」类技能。

    字面匹配有天花板：「沉没成本是……下列属于」这题本质是定义判断，
    但题干里不会出现「定义判断」四个字。这时给模块级通用方法，
    比留空有用，也比随便挑一个具体技巧更不容易误导。
    """
    candidates: list[dict] = []
    for skills in index.values():
        for skill in skills:
            module = str(skill.get("module") or "").strip()
            if module in NON_QUESTION_MODULES:
                continue
            name = str(skill.get("name") or "")
            if any(
                cue in name
                for cue in ("总体", "流程", "通用", "解题", "考点定位", "常见题型")
            ):
                candidates.append(skill)
    if not candidates:
        return []
    # 优先给有步骤的：只有名字没有步骤的「分类标签」讲不出具体做法
    candidates.sort(key=lambda item: len(item.get("steps") or []), reverse=True)
    return [candidates[0]]


def _partial_score(token: str, text: str) -> int:
    """名称和题干的最长公共子串长度。

    技能名多是组合词（「增长率计算与比较」），题干只会出现其中一部分
    （「增长率」）。取最长公共子串比整词匹配实用。
    """
    token = re.sub(r"（[^）]*）|\([^)]*\)|示例\s*\d*|\d+\s*题", "", token)
    cleaned = "".join(ch for ch in token if "\u4e00" <= ch <= "\u9fff")
    if len(cleaned) < 2:
        return 0

    # 从长到短找能在题干里找到的子串
    for length in range(len(cleaned), 1, -1):
        for start in range(len(cleaned) - length + 1):
            piece = cleaned[start : start + length]
            if piece in text:
                return length
    return 0
def _modules_of(index: dict[str, list[dict]], knowledge_point_id: str) -> set[str]:
    """从知识点 id 推断所属模块，用于限制跨知识点匹配的范围。"""
    mapping = {
        "xingce-ziliao": "资料分析",
        "xingce-shuliang": "数量关系",
        "xingce-panduan": "判断推理",
        "xingce-yanyu": "言语理解与表达",
        "xingce-changshi": "常识判断",
        "shenlun": "申论",
    }
    kp = knowledge_point_id or ""
    for key, module in mapping.items():
        if kp.startswith(key):
            return {module}
    return set()
