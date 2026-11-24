"""Extract questions from indexed material chunks and tag them finely."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Callable

import litellm
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Chunk, Question, Skill
from app.schemas.settings import LlmSettings
from app.services.llm import normalize_model, role_model_config

logger = logging.getLogger(__name__)

MAX_SCAN_CHUNKS = 2000        # 单份资料最多扫描的分块数
MAX_QUESTIONS_PER_MATERIAL = 800  # 单份资料最多抽取的题目数
LLM_BATCH_SIZE = 6            # 每次 LLM 调用处理的题目块数（长题干时输出量大）
LLM_CONCURRENCY = 4           # 并发批次数；过高容易触发供应商限流
MAX_TAGS = 6
LLM_MAX_TOKENS = 16000

ProgressCallback = Callable[[int, int], None]

OPTION_RE = re.compile(
    r"^\s*[（(]?\s*([A-D])[\s.．、:：)）]\s*(.+)$", re.MULTILINE
)
NUMBERED_RE = re.compile(r"^\s*(\d{1,3})[.．、]\s*", re.MULTILINE)

# 常用题型词典，用于规则兜底
TOPIC_HINTS: dict[str, tuple[str, ...]] = {
    "牛吃草": ("牛吃草", "草量", "吃草", "牛吃", "牧草"),
    "工程问题": ("工程", "工作效率", "合作完成"),
    "行程问题": ("行程", "速度", "相遇", "追及"),
    "利润问题": ("成本", "售价", "利润率", "打折"),
    "排列组合": ("排列", "组合", "多少种", "选法"),
    "概率问题": ("概率", "可能性", "随机"),
    "容斥问题": ("容斥", "至少", "至多", "都"),
    "最值问题": ("最值", "最大", "最小", "最不利"),
    "年龄问题": ("年龄", "岁"),
    "几何问题": ("面积", "体积", "周长", "三角形"),
    "溶液问题": ("浓度", "溶液", "溶质"),
    "鸡兔同笼": ("鸡兔同笼", "鸡兔", "兔", "笼"),
    "日期问题": ("星期", "日期", "闰年"),
    "抽屉原理": ("抽屉", "至少有一个"),
    "代入排除": ("代入", "排除"),
    "赋值法": ("赋值", "设特值"),
    "方程法": ("方程", "设未知数"),
    "比例法": ("比例", "比值"),
    "计算问题": ("计算", "速算", "估算"),
    "图形推理": ("图形", "规律", "折叠"),
    "定义判断": ("定义", "属于", "不属于"),
    "类比推理": ("类比", "关系", "相当于"),
    "逻辑判断": ("逻辑", "推理", "加强", "削弱"),
    "资料分析": ("增长率", "比重", "平均数", "倍数", "增长量"),
    "增长率计算": ("增长率", "增速", "增长百分之"),
    "基期计算": ("基期", "上年同期", "去年"),
    "增长量计算": ("增长量", "增加了", "净增"),
    "比重计算": ("占比", "比重", "占"),
    "平均数计算": ("平均数", "人均", "平均值"),
    "倍数计算": ("倍", "是…的多少倍"),
    "资料综合题": ("下列说法", "能推出", "不能推出"),
    "逻辑填空": ("填入", "最恰当", "横线"),
    "片段阅读": ("主旨", "意在说明", "作者认为"),
    "语句排序": ("排序", "顺序"),
    "常识判断": ("下列", "说法", "正确的是"),
    "科学推理": ("物理", "化学", "生物", "实验"),
    "新闻类": ("新闻", "报道", "记者", "消息"),
    "说理类": ("论证", "说明道理", "议论文"),
    "科普类": ("科学", "原理", "研究"),
    "归纳概括": ("概括", "归纳", "要点"),
    "综合分析": ("分析", "评析", "看法"),
    "提出对策": ("对策", "建议", "措施"),
    "公文写作": ("公文", "通知", "报告", "倡议"),
    "文章写作": ("作文", "议论文", "论述"),
}

SUBJECT_MODULES = {
    "资料分析": "资料分析",
    "增长率": "资料分析",
    "比重": "资料分析",
    "平均数": "资料分析",
    "数量关系": "数量关系",
    "工程问题": "数量关系",
    "行程问题": "数量关系",
    "概率问题": "数量关系",
    "排列组合": "数量关系",
    "逻辑判断": "判断推理",
    "图形推理": "判断推理",
    "定义判断": "判断推理",
    "类比推理": "判断推理",
    "逻辑填空": "言语理解与表达",
    "片段阅读": "言语理解与表达",
    "语句排序": "言语理解与表达",
    "常识判断": "常识判断",
    "科学推理": "常识判断",
    "归纳概括": "申论",
    "综合分析": "申论",
    "资料综合题": "资料分析",
    "提出对策": "申论",
    "公文写作": "申论",
    "文章写作": "申论",
}


class QuestionExtractError(RuntimeError):
    pass


# LLM 很爱自造近义标签（削弱论证/削弱质疑/削弱型…），归一到少数标准标签，
# 否则 500 道题会散出几百个只用一次的标签，筛选就失效了。
TAG_ALIASES: dict[str, str] = {
    "削弱论证": "削弱型",
    "削弱质疑": "削弱型",
    "削弱型题目": "削弱型",
    "最不能削弱": "削弱型",
    "加强论证": "加强型",
    "加强支持": "加强型",
    "加强削弱": "加强型",
    "支持论证": "加强型",
    "最不能支持": "加强型",
    "削弱建议": "削弱型",
    "前提假设": "前提型",
    "隐含前提": "前提型",
    "必要条件": "前提型",
    "假设前提": "前提型",
    "假言命题": "翻译推理",
    "条件推理": "翻译推理",
    "条件关系": "翻译推理",
    "直言命题": "翻译推理",
    "三段论": "翻译推理",
    "矛盾关系": "真假推理",
    "反对关系": "真假推理",
    "真假话": "真假推理",
    "排列组合": "分析推理",
    "排除法": "分析推理",
    "代入排除": "分析推理",
    "集合容斥": "容斥问题",
    "极值问题": "最值问题",
    "方位关系": "空间方位",
    "经济利润": "利润问题",
    "抽样调查": "统计论证",
    "统计": "统计论证",
    "数据论证": "统计论证",
    "实验论证": "实验论证",
}


# 题材/体裁统一到这几类，避免「医学健康类/医学类/医学类材料」各算一个标签。
TOPIC_TAGS: dict[str, tuple[str, ...]] = {
    "医学健康": ("医", "病", "健康", "药", "疫苗", "治疗", "症"),
    "科技": ("科技", "AI", "人工智能", "机器人", "算法", "芯片", "数字"),
    "生态环境": ("生态", "环境", "环保", "气候", "碳", "物种", "生物多样"),
    "经济商业": ("经济", "商业", "市场", "企业", "价格", "消费", "利润", "销量", "金融"),
    "社会人文": ("社会", "文化", "教育", "历史", "考古", "法律", "政策", "管理", "新闻"),
    "科普": ("科普", "科学", "研究", "实验", "原理", "推断"),
}

METHOD_TAGS: dict[str, tuple[str, ...]] = {
    "论证类": ("论证", "论据", "论点", "结论", "反驳", "质疑"),
    "实验类": ("实验", "对照", "变量", "样本"),
    "统计类": ("统计", "数据", "比例", "抽样", "调查"),
    "真假推理": ("真假", "真话", "假话"),
    "分析推理": ("排列", "匹配", "排序", "条件", "位置", "日程"),
    "翻译推理": ("命题", "条件关系", "逆否", "充分", "必要", "除非"),
}

# 后缀模式：把这些词尾巴去掉再查别名表
TAG_SUFFIXES = ("类材料", "类型", "题型", "类", "型", "题")


# 标准词表：题目标签只允许落在这些词上，保证筛选有意义。
# 由「题型（TOPIC_HINTS 的键）」+「题材」+「逻辑方法」组成。
CANONICAL_TAGS: set[str] = (
    set(TOPIC_HINTS)
    | set(TOPIC_TAGS)
    | set(METHOD_TAGS)
    | {
        "削弱型", "加强型", "前提型", "解释型", "结论型", "评价型",
        "论证结构", "统计论证", "因果论证", "类比论证", "对比论证",
        "另有他因", "因果倒置", "以偏概全", "样本偏差", "控制变量",
        "搭桥", "举反例", "排除他因", "无关项", "诉诸大众", "概念混淆",
        "平行结构", "综合推理", "朴素逻辑", "智力推理", "真假推理",
    }
)


def _strip_suffix(tag: str) -> str:
    for suffix in TAG_SUFFIXES:
        if tag.endswith(suffix) and len(tag) > len(suffix):
            return tag[: -len(suffix)]
    return tag


def _canonicalize(tag: str) -> str:
    """把一个标签尽量映射到标准词表，映射不到返回空串。"""
    stripped = _strip_suffix(tag)
    for candidate in (tag, stripped):
        if candidate in CANONICAL_TAGS:
            return candidate
        if candidate in TAG_ALIASES:
            return TAG_ALIASES[candidate]
        # 「科普类」剥后缀后是「科普」，但「新闻类」剥成「新闻」不在词表里
        for standard in CANONICAL_TAGS:
            if standard == candidate or f"{candidate}类" == standard:
                return standard
    for topic, cues in TOPIC_TAGS.items():
        if any(cue in tag for cue in cues):
            return topic
    for method, cues in METHOD_TAGS.items():
        if any(cue in tag for cue in cues):
            return method
    return ""


def _normalize_tags(tags: list[str]) -> list[str]:
    """收敛到标准词表并去重，保持首次出现的顺序。

    长尾标签（自造体裁描述、同义变体）不再原样入库，否则 500 道题会散出几百个
    只出现一次的词，标签筛选就失效了。
    """
    merged: list[str] = []
    for tag in tags:
        value = _canonicalize(tag)
        if value and value not in merged:
            merged.append(value)
    return merged[:MAX_TAGS]



def _clean(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _parse_options(text: str) -> tuple[str, list[dict]]:
    """Split stem from options. Returns (stem, options).

    PDF extraction often repeats the last option lines at a page break, so a
    repeated key with identical text is dropped.
    """
    matches = list(OPTION_RE.finditer(text))
    if len(matches) < 2:
        return _clean(text), []
    first = matches[0]
    stem = _clean(text[: first.start()])
    options: list[dict] = []
    seen: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        key = match.group(1)
        value = _clean(text[match.start(2) : end])
        if not value:
            continue
        if key in seen:
            # 同字母重复：内容相同就跳过，不同则保留第一个并加后缀避免覆盖
            if seen[key] == value:
                continue
            continue
        seen[key] = value
        options.append({"key": key, "text": value})
    return stem, options


def _rule_tags(stem: str, module: str) -> list[str]:
    tags: list[str] = []
    for tag, cues in TOPIC_HINTS.items():
        if any(cue in stem for cue in cues):
            tags.append(tag)
        if len(tags) >= MAX_TAGS:
            break
    if module and module not in tags:
        tags.insert(0, module)
    return tags[:MAX_TAGS]


def _guess_module(tags: list[str], default: str = "") -> str:
    for tag in tags:
        module = SUBJECT_MODULES.get(tag)
        if module:
            return module
    return default


def _load_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        value = json.loads(cleaned, strict=False)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            return {}
        try:
            value = json.loads(cleaned[start : end + 1], strict=False)
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}


TOC_RE = re.compile(r"^\s*练习题\s*\d{2}\s*\d{0,4}\s*$")


def _is_toc(text: str) -> bool:
    """A table-of-contents block: most lines are 练习题 NN, no question marks."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return True
    toc_lines = sum(1 for line in lines if TOC_RE.match(line))
    if toc_lines / len(lines) < 0.6:
        return False
    return "？" not in text and "?" not in text and not OPTION_RE.search(text)


def _looks_like_question(block: str) -> bool:
    if len(block) < 30:
        return False
    has_prompt = "？" in block or "?" in block
    options = len(OPTION_RE.findall(block))
    return has_prompt or options >= 2


def split_questions(text: str, limit: int = 40) -> list[str]:
    """Split one chunk into candidate question blocks."""
    if _is_toc(text):
        return []
    blocks: list[str] = []
    marks = list(NUMBERED_RE.finditer(text))
    if len(marks) >= 2:
        for index, match in enumerate(marks):
            start = match.start()
            end = marks[index + 1].start() if index + 1 < len(marks) else len(text)
            block = text[start:end].strip()
            if _looks_like_question(block):
                blocks.append(block)
    if not blocks and _looks_like_question(text):
        blocks = [text]
    # 片段开头不是题号的，接回上一题（选项被切到下一段的情况）
    # 片段开头不是题号的，接回上一题（选项被切到下一段的情况）
    option_start = re.compile(r"^\s*[A-DＡ-Ｄ][\s.．、:：)）]")
    merged: list[str] = []
    for block in blocks:
        starts_number = bool(re.match(r"^\s*\d{1,3}[.．、]", block))
        if merged and (option_start.match(block) or not starts_number):
            merged[-1] = f"{merged[-1]}\n{block}"
        else:
            merged.append(block)
    return [block for block in merged if len(block) >= 30][:limit]


def split_material(
    chunks: list[tuple[str, str]],
    limit: int = 800,
) -> list[tuple[str, str]]:
    """Split a whole material into question blocks, stitching across chunks.

    Args:
        chunks: [(chunk_id, content)] in reading order.

    Returns:
        [(chunk_id, block)]; a block that spans two chunks is attributed to the
        chunk it started in.
    """
    results: list[tuple[str, str]] = []
    # 先按分块累积文本，跨块把「题号缺失的续行」接回上一块
    merged: list[tuple[str, str]] = []
    option_start = re.compile(r"^\s*[A-DＡ-Ｄ][\s.．、:：)）]")
    number_start = re.compile(r"^\s*\d{1,3}[.．、]")
    for chunk_id, content in chunks:
        stripped = content.lstrip()
        if (
            merged
            and stripped
            and (option_start.match(stripped) or not number_start.match(stripped))
        ):
            merged[-1] = (merged[-1][0], f"{merged[-1][1]}\n{content}")
        else:
            merged.append((chunk_id, content))

    for chunk_id, content in merged:
        if len(results) >= limit:
            break
        for block in split_questions(content, limit=limit - len(results)):
            results.append((chunk_id, block))
    return results


def _build_prompt(questions: list[str], skill_names: list[str]) -> str:
    skill_line = "、".join(skill_names[:80])
    blocks = "\n\n".join(
        f"[{index}] {block[:2000]}" for index, block in enumerate(questions)
    )
    return (
        "你是公务员考试题库整理专家。请判断下面每段内容是否是一道完整的题目，"
        "如果是，给出细粒度标签。\n"
        "标签要具体：例如「牛吃草」「概率问题」「工程问题」「逻辑填空」"
        "「新闻类」「说理类」「科普类」「归纳概括」。每道题给 2–5 个标签，"
        "从具体题型到材料体裁都可以。\n"
        "只返回 JSON，不要 Markdown：\n"
        '{"questions":[{"index":0,"is_question":true,"type":"single",'
        '"subject":"行测","module":"数量关系","stem":"...",'
        '"options":[{"key":"A","text":"..."}],"answer":"B",'
        '"explanation":"...","tags":["牛吃草","工程问题"],"difficulty":3}]}\n'
        "要求：\n"
        "1. is_question 为 false 的内容直接跳过。\n"
        "2. stem 只保留题干，不要带选项；options 按 A/B/C/D 拆开；"
        "没有选项就留空数组，type 填 short。\n"
        "3. answer 只填选项字母；不确定就留空。\n"
        "4. tags 必须具体，不要只写「数量关系」这种大模块。\n"
        "5. difficulty 为 1–5 的整数。\n"
        f"可选技能参考：{skill_line}\n\n"
        "内容：\n" + blocks
    )


async def _llm_questions(
    db: AsyncSession,
    blocks: list[str],
    llm: LlmSettings,
    skill_names: list[str] | None = None,
) -> list[dict]:
    if get_settings().mock_llm:
        raise QuestionExtractError("mock mode")
    endpoint = role_model_config(llm, "knowledge")
    if not endpoint.model:
        raise QuestionExtractError("knowledge model not configured")

    if skill_names is None:
        skill_names = [
            row.name for row in (await db.execute(select(Skill))).scalars()
        ]
    kwargs: dict = {
        "model": normalize_model(endpoint.model),
        "messages": [
            {
                "role": "system",
                "content": "你是严谨的考公题库整理专家，只输出 JSON。",
            },
            {
                "role": "user",
                "content": _build_prompt(blocks, skill_names),
            },
        ],
        "temperature": 0.2,
        "max_tokens": max(endpoint.max_tokens or 0, LLM_MAX_TOKENS),
        "timeout": 180,
        "response_format": {"type": "json_object"},
    }
    if endpoint.api_base:
        kwargs["api_base"] = endpoint.api_base
    if endpoint.api_key:
        kwargs["api_key"] = endpoint.api_key

    if len(blocks) > 1:
        try:
            return await _call_llm(blocks, kwargs)
        except QuestionExtractError as exc:
            if "truncated" not in str(exc):
                raise
            middle = len(blocks) // 2
            logger.info("splitting question batch of %s after truncation", len(blocks))
            first = await _llm_questions(db, blocks[:middle], llm, skill_names)
            second = await _llm_questions(db, blocks[middle:], llm, skill_names)
            for item in second:
                item["chunk_index"] = item.get("chunk_index", 0) + middle
            return first + second
    return await _call_llm(blocks, kwargs)


def _fill_missing(
    blocks: list[str],
    items: list[dict],
    default_module: str = "",
) -> list[dict]:
    """LLM 偶尔漏判个别块；带完整选项的块用规则补回来，别丢题。"""
    seen = {item.get("chunk_index") for item in items}
    extras: list[dict] = []
    for index, block in enumerate(blocks):
        if index in seen:
            continue
        stem, options = _parse_options(block)
        if len(options) < 2 or len(block.strip()) < 30:
            continue
        tags = _rule_tags(stem, default_module)
        extras.append(
            {
                "chunk_index": index,
                "type": "single",
                "subject": "行测",
                "module": _guess_module(tags, default_module)[:64],
                "stem": stem[:4000],
                "options": options,
                "answer": "",
                "explanation": "",
                "tags": tags,
                "difficulty": 3,
            }
        )
    return items + extras


async def _call_llm(blocks: list[str], kwargs: dict) -> list[dict]:
    response = await litellm.acompletion(**kwargs)
    choice = response.choices[0]
    if getattr(choice, "finish_reason", "") == "length":
        raise QuestionExtractError("LLM output truncated")
    payload = _load_json(str(choice.message.content or ""))
    items = payload.get("questions")
    if not isinstance(items, list):
        raise QuestionExtractError("LLM returned no questions")

    parsed: list[dict] = []
    for item in items:
        if not isinstance(item, dict) or not item.get("is_question"):
            continue
        try:
            index = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        if index < 0 or index >= len(blocks):
            continue
        stem = str(item.get("stem") or "").strip()
        if len(stem) < 10:
            continue
        options = []
        raw_options = item.get("options")
        if isinstance(raw_options, list):
            for option in raw_options:
                if isinstance(option, dict) and option.get("key"):
                    options.append(
                        {
                            "key": str(option["key"])[:2],
                            "text": str(option.get("text") or "").strip()[:500],
                        }
                    )
        tags = [
            str(tag).strip()[:32]
            for tag in (item.get("tags") or [])
            if str(tag).strip()
        ][:MAX_TAGS]
        module = str(item.get("module") or "").strip()
        if not module:
            module = _guess_module(tags)
        parsed.append(
            {
                "chunk_index": index,
                "type": str(item.get("type") or ("single" if options else "short")),
                "subject": str(item.get("subject") or "行测").strip()[:32],
                "module": module[:64],
                "stem": stem[:4000],
                "options": options,
                "answer": str(item.get("answer") or "").strip()[:8],
                "explanation": str(item.get("explanation") or "").strip()[:2000],
                "tags": _normalize_tags(tags) or _rule_tags(stem, module),
                "difficulty": max(1, min(5, int(item.get("difficulty") or 3))),
            }
        )
    if not parsed:
        raise QuestionExtractError("LLM returned no valid questions")
    return parsed


def _rule_questions(blocks: list[str], default_module: str = "") -> list[dict]:
    """Fallback: keep anything that looks like a question with options."""
    parsed: list[dict] = []
    for index, block in enumerate(blocks):
        stem, options = _parse_options(block)
        if len(options) < 2 and "？" not in stem and "?" not in stem:
            continue
        if len(stem) < 10:
            continue
        tags = _rule_tags(stem, default_module)
        parsed.append(
            {
                "chunk_index": index,
                "type": "single" if options else "short",
                "subject": "行测",
                "module": _guess_module(tags, default_module)[:64],
                "stem": stem[:4000],
                "options": options,
                "answer": "",
                "explanation": "",
                "tags": tags,
                "difficulty": 3,
            }
        )
    return parsed


def _format_tags(tags: list[str]) -> str:
    return json.dumps(tags, ensure_ascii=False)


def _question_id(material_id: str, chunk_id: str, stem: str) -> str:
    import hashlib

    digest = hashlib.sha1(
        f"{material_id}|{chunk_id}|{stem[:200]}".encode()
    ).hexdigest()[:16]
    return f"q-{digest}"


async def extract_questions(
    db: AsyncSession,
    material_id: str,
    llm: LlmSettings,
    progress: ProgressCallback | None = None,
) -> dict:
    """Scan a material's chunks, extract questions and tag them.

    Long materials are processed in LLM-sized batches; one failed batch falls
    back to rule extraction instead of losing the rest.
    """
    await db.execute(delete(Question).where(Question.material_id == material_id))

    chunks = list(
        (
            await db.execute(
                select(Chunk)
                .where(Chunk.material_id == material_id)
                .order_by(Chunk.chunk_index)
                .limit(MAX_SCAN_CHUNKS)
            )
        ).scalars()
    )
    if not chunks:
        await db.commit()
        return {"questions": 0, "model": "", "warning": ""}

    pairs = split_material(
        [(chunk.id, chunk.content) for chunk in chunks],
        limit=MAX_QUESTIONS_PER_MATERIAL,
    )
    if not pairs:
        await db.commit()
        return {"questions": 0, "model": "", "warning": ""}

    by_id = {chunk.id: chunk for chunk in chunks}
    blocks = [block for _, block in pairs]
    owners = [by_id[chunk_id] for chunk_id, _ in pairs]

    warning = ""
    items: list[dict] = []
    model_used = "rule"
    batches = [
        (start, min(start + LLM_BATCH_SIZE, len(blocks)))
        for start in range(0, len(blocks), LLM_BATCH_SIZE)
    ]

    skill_names = [
        row.name for row in (await db.execute(select(Skill))).scalars()
    ]
    semaphore = asyncio.Semaphore(LLM_CONCURRENCY)
    done = 0
    llm_failed = 0
    lock = asyncio.Lock()

    async def run_batch(index: int, start: int, end: int) -> list[dict]:
        batch_blocks = blocks[start:end]
        async with semaphore:
            try:
                items_out = await _llm_questions(db, batch_blocks, llm, skill_names)
                items_out = _fill_missing(batch_blocks, items_out)
            except Exception as exc:  # noqa: BLE001 - keep going with rules
                logger.warning("question batch %s failed: %s", index, exc)
                items_out = _rule_questions(batch_blocks)
                async with lock:
                    nonlocal llm_failed, done
                    llm_failed += 1
            for offset, item in enumerate(items_out):
                position = start + item.pop("chunk_index", offset)
                if 0 <= position < len(owners):
                    item["chunk"] = owners[position]
        async with lock:
            done += 1
            if progress is not None:
                try:
                    progress(done, len(batches))
                except Exception:
                    logger.debug("progress callback failed", exc_info=True)
        return items_out

    results = await asyncio.gather(
        *(
            run_batch(index, start, end)
            for index, (start, end) in enumerate(batches, start=1)
        )
    )
    for batch_items in results:
        items.extend(batch_items)
    model_used = role_model_config(llm, "knowledge").model

    if llm_failed:
        warning = f"{llm_failed}/{len(batches)} 批 LLM 识别失败，已用规则补齐。"

    created = 0
    seen: set[str] = set()
    for item in items:
        chunk: Chunk | None = item.get("chunk")
        if chunk is None:
            continue
        qid = _question_id(material_id, chunk.id, item["stem"])
        if qid in seen:
            continue
        seen.add(qid)
        answer = item.get("answer") or ""
        db.add(
            Question(
                id=qid,
                type=item["type"],
                subject=item["subject"],
                module=item["module"],
                knowledge_point_id=chunk.knowledge_point_id,
                knowledge_point_name=chunk.knowledge_point_name,
                stem=item["stem"],
                options_json=json.dumps(item["options"], ensure_ascii=False),
                answer_json=json.dumps(
                    {"value": answer.upper()} if answer else {}, ensure_ascii=False
                ),
                explanation=item.get("explanation", ""),
                difficulty=item.get("difficulty", 3),
                source="material",
                material_id=material_id,
                tags_json=_format_tags(item.get("tags") or []),
                quality_status="approved",
            )
        )
        created += 1

    await db.commit()
    return {"questions": created, "model": model_used, "warning": warning}
