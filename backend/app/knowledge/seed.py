"""Knowledge tree seed data and idempotent seeding."""

import json
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeCard, KnowledgePoint


@dataclass(frozen=True)
class KPNode:
    id: str
    name: str
    subject: str
    module: str
    parent_id: str | None
    keywords: tuple[str, ...]
    description: str = ""
    level: int = 1
    sort_order: int = 0


KNOWLEDGE_TREE: tuple[KPNode, ...] = (
    KPNode("xingce", "行测", "行测", "", None, (), "行政职业能力测验", 1, 10),
    KPNode(
        "xingce-yanyu",
        "言语理解与表达",
        "行测",
        "言语理解与表达",
        "xingce",
        ("言语理解",),
        "言语理解与表达模块",
        2,
        10,
    ),
    KPNode(
        "xingce-yanyu-luoji",
        "逻辑填空",
        "行测",
        "言语理解与表达",
        "xingce-yanyu",
        ("逻辑填空", "实词辨析", "成语辨析", "语境", "呼应点", "感情色彩", "搭配"),
        "逻辑填空：语境分析与词语辨析",
        3,
        10,
    ),
    KPNode(
        "xingce-yanyu-pianduan",
        "片段阅读",
        "行测",
        "言语理解与表达",
        "xingce-yanyu",
        ("片段阅读", "主旨", "意图判断", "细节判断", "标题填入", "语句衔接"),
        "片段阅读：主旨、意图与细节",
        3,
        20,
    ),
    KPNode(
        "xingce-yanyu-yuju",
        "语句表达",
        "行测",
        "言语理解与表达",
        "xingce-yanyu",
        ("语句表达", "语句排序", "语句衔接", "病句", "歧义"),
        "语句表达：排序、衔接与病句",
        3,
        30,
    ),
    KPNode(
        "xingce-shuliang",
        "数量关系",
        "行测",
        "数量关系",
        "xingce",
        ("数量关系",),
        "数量关系模块",
        2,
        20,
    ),
    KPNode(
        "xingce-shuliang-yunsuan",
        "数学运算",
        "行测",
        "数量关系",
        "xingce-shuliang",
        ("数学运算", "行程", "工程", "利润", "排列组合", "概率", "几何", "容斥"),
        "数学运算常见题型",
        3,
        10,
    ),
    KPNode(
        "xingce-shuliang-shuzi",
        "数字推理",
        "行测",
        "数量关系",
        "xingce-shuliang",
        ("数字推理", "数列", "等差数列", "等比数列", "递推数列"),
        "数字推理：数列规律",
        3,
        20,
    ),
    KPNode(
        "xingce-panduan",
        "判断推理",
        "行测",
        "判断推理",
        "xingce",
        ("判断推理",),
        "判断推理模块",
        2,
        30,
    ),
    KPNode(
        "xingce-panduan-tuxing",
        "图形推理",
        "行测",
        "判断推理",
        "xingce-panduan",
        ("图形推理", "位置规律", "样式规律", "属性规律", "数量规律", "空间重构"),
        "图形推理：位置、样式、属性、数量、空间",
        3,
        10,
    ),
    KPNode(
        "xingce-panduan-dingyi",
        "定义判断",
        "行测",
        "判断推理",
        "xingce-panduan",
        ("定义判断", "被定义项", "关键信息", "要件"),
        "定义判断：抓关键信息",
        3,
        20,
    ),
    KPNode(
        "xingce-panduan-leibi",
        "类比推理",
        "行测",
        "判断推理",
        "xingce-panduan",
        ("类比推理", "逻辑关系", "言语关系", "经验常识"),
        "类比推理：找关系",
        3,
        30,
    ),
    KPNode(
        "xingce-panduan-luoji",
        "逻辑判断",
        "行测",
        "判断推理",
        "xingce-panduan",
        ("逻辑判断", "削弱", "加强", "前提假设", "翻译推理", "真假推理", "因果"),
        "逻辑判断：论证与推理",
        3,
        40,
    ),
    KPNode(
        "xingce-ziliao",
        "资料分析",
        "行测",
        "资料分析",
        "xingce",
        ("资料分析",),
        "资料分析模块",
        2,
        40,
    ),
    KPNode(
        "xingce-ziliao-susuan",
        "速算技巧",
        "行测",
        "资料分析",
        "xingce-ziliao",
        ("速算", "截位直除", "直除", "化同", "差分法", "特征数字", "估算", "有效数字"),
        "资料分析速算：截位、化同、差分、特征数字",
        3,
        10,
    ),
    KPNode(
        "xingce-ziliao-zengzhang",
        "增长率",
        "行测",
        "资料分析",
        "xingce-ziliao",
        ("增长率", "增长量", "基期", "现期", "隔年增长", "混合增长", "同比", "环比"),
        "增长率与基期计算",
        3,
        20,
    ),
    KPNode(
        "xingce-ziliao-bizhong",
        "比重",
        "行测",
        "资料分析",
        "xingce-ziliao",
        ("比重", "占比", "部分", "整体", "比重差", "两期比重"),
        "比重与两期比重比较",
        3,
        30,
    ),
    KPNode(
        "xingce-ziliao-pingjun",
        "平均数",
        "行测",
        "资料分析",
        "xingce-ziliao",
        ("平均数", "平均增长", "人均", "均值"),
        "平均数与平均增长",
        3,
        40,
    ),
    KPNode(
        "xingce-ziliao-beishu",
        "倍数",
        "行测",
        "资料分析",
        "xingce-ziliao",
        ("倍数", "翻番", "是几倍", "多几倍"),
        "倍数与翻番",
        3,
        50,
    ),
    KPNode(
        "xingce-changshi",
        "常识判断",
        "行测",
        "常识判断",
        "xingce",
        ("常识判断",),
        "常识判断模块",
        2,
        50,
    ),
    KPNode(
        "xingce-changshi-zhengzhi",
        "政治常识",
        "行测",
        "常识判断",
        "xingce-changshi",
        ("政治常识", "时政", "马克思主义", "党史"),
        "政治常识",
        3,
        10,
    ),
    KPNode(
        "xingce-changshi-falv",
        "法律常识",
        "行测",
        "常识判断",
        "xingce-changshi",
        ("法律常识", "宪法", "民法", "刑法", "行政法"),
        "法律常识",
        3,
        20,
    ),
    KPNode(
        "xingce-changshi-jingji",
        "经济常识",
        "行测",
        "常识判断",
        "xingce-changshi",
        ("经济常识", "宏观经济", "财政", "货币", "市场"),
        "经济常识",
        3,
        30,
    ),
    KPNode("shenlun", "申论", "申论", "", None, (), "申论科目", 1, 20),
    KPNode(
        "shenlun-guina",
        "归纳概括",
        "申论",
        "归纳概括",
        "shenlun",
        ("归纳概括", "概括题", "归纳", "要点", "分条", "同义合并"),
        "归纳概括：找点、合并、分条",
        2,
        10,
    ),
    KPNode(
        "shenlun-fenxi",
        "综合分析",
        "申论",
        "综合分析",
        "shenlun",
        ("综合分析", "分析题", "解释", "评价", "启示", "观点"),
        "综合分析：解释、评价、启示",
        2,
        20,
    ),
    KPNode(
        "shenlun-duice",
        "提出对策",
        "申论",
        "提出对策",
        "shenlun",
        ("提出对策", "对策题", "建议", "措施", "方案"),
        "提出对策：问题—原因—对策",
        2,
        30,
    ),
    KPNode(
        "shenlun-guanche",
        "贯彻执行",
        "申论",
        "贯彻执行",
        "shenlun",
        ("贯彻执行", "公文", "倡议书", "讲话稿", "宣传稿", "简报"),
        "贯彻执行：公文格式与内容",
        2,
        40,
    ),
    KPNode(
        "shenlun-zuowen",
        "文章写作",
        "申论",
        "文章写作",
        "shenlun",
        ("文章写作", "大作文", "申论作文", "立意", "分论点", "论证"),
        "文章写作：立意、结构、论证",
        2,
        50,
    ),
)


KNOWLEDGE_CARDS: dict[str, dict[str, str]] = {
    "xingce-ziliao-susuan": {
        "summary": "资料分析速算：先看选项差距，再决定截位；常用截位直除、化同、差分法、特征数字、比重比较。",
        "methods": "1. 截位直除：保留前三位，分母截位方向一致。\n2. 化同：把分子分母化成相近的数，便于比较。\n3. 差分法：比较两个分数时，用差分数与小数比较。\n4. 特征数字：1/6≈16.7%，1/7≈14.3%，1/8=12.5%，1/9≈11.1%。\n5. 比重比较：看部分增速与整体增速的大小关系。",
        "traps": "截位方向不一致；选项差距小还过度截位；差分法正负号写错；百分数与百分点混淆。",
    },
    "xingce-ziliao-zengzhang": {
        "summary": "增长率=(现期-基期)/基期；基期=现期/(1+r)；隔年增长率=r1+r2+r1×r2；混合增长率介于两部分之间。",
        "methods": "先判断题型：求增长率、求基期、求现期、求隔年、求混合。套公式前先统一单位。",
        "traps": "增长率与增长量混淆；百分数与百分点混淆；隔年增长率漏掉交叉项。",
    },
    "xingce-ziliao-bizhong": {
        "summary": "比重=部分/整体；比重变化看部分增速与整体增速的大小关系。",
        "methods": "现期比重=A/B；基期比重=A/B×(1+b)/(1+a)；比重差用百分点。",
        "traps": "部分与整体颠倒；把比重差写成增长率；忘记分母的增速。",
    },
    "xingce-panduan-tuxing": {
        "summary": "图形推理先看图形组成是否相同：相同看位置/样式，不同看属性/数量/空间。",
        "methods": "位置规律、样式规律、属性规律、数量规律、空间重构。",
        "traps": "只看一个规律；忽略图形间运算；空间重构方向看反。",
    },
    "xingce-panduan-luoji": {
        "summary": "逻辑判断先找论点论据，再判断加强/削弱；翻译推理记关联词规则。",
        "methods": "削弱加强、前提假设、翻译推理、真假推理；削弱优先找切断联系。",
        "traps": "无关项；偷换概念；因果倒置；把必要条件当充分条件。",
    },
    "xingce-yanyu-luoji": {
        "summary": "逻辑填空=语境分析+词语辨析；关注关联词、感情色彩、搭配范围。",
        "methods": "先找呼应点，再辨词义侧重、程度轻重、搭配对象、语体色彩。",
        "traps": "望文生义；语体不符；只凭语感不看语境。",
    },
    "shenlun-guina": {
        "summary": "归纳概括：审题定对象，回材料找要点，同义合并，分条书写。",
        "methods": "先划关键词，再合并同类，最后按逻辑排序；尽量使用材料原词。",
        "traps": "要点不全；照抄整段；不分条；超字数。",
    },
    "shenlun-zuowen": {
        "summary": "文章写作：立意准确、结构清晰、论证充分、语言规范。",
        "methods": "标题—开头—分论点—结尾；分论点从材料中提炼，论证用材料+分析。",
        "traps": "跑题；分论点重复；空喊口号；结构失衡。",
    },
}


async def seed_knowledge_tree(db: AsyncSession) -> None:
    """Insert or refresh the built-in taxonomy and create missing cards."""
    for node in KNOWLEDGE_TREE:
        existing = await db.get(KnowledgePoint, node.id)
        values = {
            "parent_id": node.parent_id,
            "name": node.name,
            "subject": node.subject,
            "module": node.module,
            "description": node.description,
            "keywords_json": json.dumps(list(node.keywords), ensure_ascii=False),
            "level": node.level,
            "sort_order": node.sort_order,
        }
        if existing is None:
            db.add(KnowledgePoint(id=node.id, **values))
        else:
            for key, value in values.items():
                setattr(existing, key, value)

    await db.flush()

    for node in KNOWLEDGE_TREE:
        existing_card = await db.get(KnowledgeCard, node.id)
        if existing_card is not None:
            continue
        curated = KNOWLEDGE_CARDS.get(node.id, {})
        db.add(
            KnowledgeCard(
                id=node.id,
                title=node.name,
                summary=curated.get("summary", node.description),
                methods=curated.get("methods", ""),
                traps=curated.get("traps", ""),
            )
        )

    await db.commit()
