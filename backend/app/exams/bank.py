"""Deterministic synthetic question bank for the local P2 demo."""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Question


def _numeric_options(
    correct: float,
    step: float,
    rotate: int,
    unit: str = "",
    decimals: int = 1,
) -> tuple[list[dict], str]:
    candidates = [correct, correct + step, correct - step, correct + 2 * step]
    clean: list[float] = []
    for value in candidates:
        value = round(value, decimals)
        while value <= 0 or any(
            abs(value - item) < 10 ** (-decimals) for item in clean
        ):
            value = round(value + step, decimals)
        clean.append(value)

    correct_value = clean[0]
    others = clean[1:]
    index = rotate % 4
    ordered = others.copy()
    ordered.insert(index, correct_value)
    keys = "ABCD"
    options = [
        {"key": keys[i], "text": f"{ordered[i]:.{decimals}f}{unit}"}
        for i in range(4)
    ]
    return options, keys[index]


def _text_options(
    correct: str, distractors: list[str], rotate: int
) -> tuple[list[dict], str]:
    ordered = distractors[:3]
    index = rotate % 4
    ordered.insert(index, correct)
    keys = "ABCD"
    options = [{"key": keys[i], "text": ordered[i]} for i in range(4)]
    return options, keys[index]


def _question(
    qid: str,
    stem: str,
    options: list[dict],
    answer: str,
    explanation: str,
    kp_id: str,
    kp_name: str,
    difficulty: int,
    *,
    subject: str = "行测",
    module: str = "资料分析",
) -> dict:
    return {
        "id": qid,
        "type": "single",
        "subject": subject,
        "module": module,
        "knowledge_point_id": kp_id,
        "knowledge_point_name": kp_name,
        "stem": stem,
        "options_json": json.dumps(options, ensure_ascii=False),
        "answer_json": json.dumps({"value": answer}, ensure_ascii=False),
        "rubric_json": "[]",
        "explanation": explanation,
        "difficulty": difficulty,
        "source": "seed",
        "quality_status": "approved",
    }


def _short(
    qid: str,
    stem: str,
    reference: str,
    rubric: list[dict],
    kp_id: str,
    kp_name: str,
    *,
    subject: str = "行测",
    module: str = "资料分析",
    difficulty: int = 3,
) -> dict:
    return {
        "id": qid,
        "type": "short",
        "subject": subject,
        "module": module,
        "knowledge_point_id": kp_id,
        "knowledge_point_name": kp_name,
        "stem": stem,
        "options_json": "[]",
        "answer_json": json.dumps({"reference": reference}, ensure_ascii=False),
        "rubric_json": json.dumps(rubric, ensure_ascii=False),
        "explanation": reference,
        "difficulty": difficulty,
        "source": "seed",
        "quality_status": "approved",
    }


def _yanyu_questions() -> list[dict]:
    questions: list[dict] = []
    fills = [
        (
            "面对复杂局面，领导干部要善于抓住主要矛盾，做到________。",
            "纲举目张",
            ["面面俱到", "按部就班", "因噎废食"],
            "抓住主要矛盾、带动全局，对应“纲举目张”。",
        ),
        (
            "科学研究需要长期积累，不能________，否则很难取得原创性成果。",
            "急功近利",
            ["循序渐进", "持之以恒", "脚踏实地"],
            "与“长期积累”相对，应填“急功近利”。",
        ),
        (
            "对错误观点不能________，必须旗帜鲜明地反对。",
            "姑息迁就",
            ["防微杜渐", "未雨绸缪", "居安思危"],
            "对错误观点态度含糊，对应“姑息迁就”。",
        ),
        (
            "城市建设要________，避免千城一面。",
            "因地制宜",
            ["千篇一律", "照搬照抄", "削足适履"],
            "避免千城一面，强调根据本地实际，选“因地制宜”。",
        ),
        (
            "面对突发疫情，医护人员________，冲在最前线。",
            "义无反顾",
            ["瞻前顾后", "优柔寡断", "畏首畏尾"],
            "语境为正面赞扬，选“义无反顾”。",
        ),
        (
            "网络空间不是法外之地，治理要________，既治标也治本。",
            "标本兼治",
            ["扬汤止沸", "隔靴搔痒", "头痛医头"],
            "“既治标也治本”直接对应“标本兼治”。",
        ),
    ]
    for index, (stem, correct, distractors, explanation) in enumerate(fills, 1):
        options, answer = _text_options(correct, distractors, index)
        questions.append(
            _question(
                f"seed-yanyu-luoji-{index:02d}",
                stem,
                options,
                answer,
                explanation,
                "xingce-yanyu-luoji",
                "逻辑填空",
                [2, 3, 3, 4][index % 4],
                module="言语理解与表达",
            )
        )

    passages = [
        (
            (
                "数字技术正在深刻改变政务服务。过去群众办事要跑多个窗口，如今通过政务平台，"
                "很多事项可以“一网通办”。但技术只是手段，如果流程不优化、数据不共享，"
                "群众仍然会在部门之间来回奔波。只有以群众需求为出发点重构流程，"
                "才能真正实现“数据多跑路、群众少跑腿”。"
            ),
            "数字政务应以群众需求为导向",
            ["数字技术可以解决所有政务问题", "政务平台建设应优先采购先进设备", "窗口服务应当全部取消"],
            "文段重点是技术之外还要优化流程、共享数据，落脚点是群众需求。",
        ),
        (
            (
                "塑料污染治理不能只依靠末端回收。回收体系再完善，也难以消化不断增长的塑料垃圾。"
                "从源头减少一次性塑料制品使用，推动可循环包装替代，才是解决问题的关键。"
            ),
            "治理塑料污染需要从源头减量",
            ["回收体系已经十分完善", "塑料制品应全面禁止生产", "消费者应承担全部治理责任"],
            "“不能只依靠末端回收”“源头减少”点明主旨。",
        ),
        (
            (
                "在信息爆炸的时代，人们获取资讯越来越容易，但专注阅读一本厚书却越来越难。"
                "碎片化阅读能带来即时满足，却难以形成系统思考。越是在这样的环境中，"
                "越需要为深度阅读留出时间。"
            ),
            "信息时代更应重视深度阅读",
            ["碎片化阅读完全没有价值", "纸质书一定优于电子书", "人们已经不再需要阅读"],
            "文段承认碎片化阅读的存在，但强调深度阅读的必要性。",
        ),
        (
            (
                "城市更新不是简单地推倒重建。老街区承载着城市记忆和居民情感，"
                "更新过程中应尽可能保留历史建筑和原有肌理，让新功能与老空间有机融合。"
            ),
            "城市更新要注重保护历史文脉",
            ["城市更新必须停止", "老街区应全部改造成商业区", "历史建筑都比新建筑更有价值"],
            "“保留历史建筑和原有肌理”对应保护历史文脉。",
        ),
    ]
    for index, (stem, correct, distractors, explanation) in enumerate(
        passages, 1
    ):
        options, answer = _text_options(correct, distractors, index + 1)
        questions.append(
            _question(
                f"seed-yanyu-pianduan-{index:02d}",
                stem + "\n\n这段文字意在说明：",
                options,
                answer,
                explanation,
                "xingce-yanyu-pianduan",
                "片段阅读",
                [2, 3, 3, 4][index % 4],
                module="言语理解与表达",
            )
        )
    return questions


def _shuliang_questions() -> list[dict]:
    questions: list[dict] = []

    engineering = [(12, 6), (10, 15), (8, 24)]
    for index, (first, second) in enumerate(engineering, 1):
        days = first * second / (first + second)
        options, answer = _numeric_options(days, 0.5, index, "天")
        questions.append(
            _question(
                f"seed-shuliang-gongcheng-{index:02d}",
                f"一项工程，甲单独做需要 {first} 天，乙单独做需要 {second} 天。"
                "两人合作完成这项工程需要多少天？",
                options,
                answer,
                f"合作效率=1/{first}+1/{second}，合作时间={first}×{second}÷"
                f"({first}+{second})≈{days:.1f}天。",
                "xingce-shuliang-yunsuan",
                "数学运算",
                [2, 3, 3][index % 3],
                module="数量关系",
            )
        )

    trips = [(360, 90), (420, 70), (240, 80)]
    for index, (distance, speed) in enumerate(trips, 1):
        hours = distance / speed
        options, answer = _numeric_options(hours, 0.5, index + 1, "小时")
        questions.append(
            _question(
                f"seed-shuliang-xingcheng-{index:02d}",
                f"甲、乙两地相距 {distance} 千米，一辆汽车以每小时 {speed} 千米的"
                "速度匀速行驶，从甲地到乙地需要多少小时？",
                options,
                answer,
                f"时间=路程÷速度={distance}÷{speed}={hours:.1f}小时。",
                "xingce-shuliang-yunsuan",
                "数学运算",
                [2, 3, 3][index % 3],
                module="数量关系",
            )
        )

    profits = [(200, 25), (480, 15), (360, 20)]
    for index, (cost, markup) in enumerate(profits, 1):
        price = cost * (1 + markup / 100)
        options, answer = _numeric_options(price, 20, index + 2, "元")
        questions.append(
            _question(
                f"seed-shuliang-lirun-{index:02d}",
                f"某商品进价为 {cost} 元，按进价的 {markup}% 加价出售，售价是多少元？",
                options,
                answer,
                f"售价=进价×(1+加价率)={cost}×{1 + markup / 100:.2f}={price:.0f}元。",
                "xingce-shuliang-yunsuan",
                "数学运算",
                [2, 3, 3][index % 3],
                module="数量关系",
            )
        )

    combinations = [6, 8, 10]
    for index, total in enumerate(combinations, 1):
        ways = total * (total - 1) // 2
        options, answer = _numeric_options(ways, 3, index, "种")
        questions.append(
            _question(
                f"seed-shuliang-zuhe-{index:02d}",
                f"从 {total} 名同学中选出 2 人参加活动，共有多少种不同的选法？",
                options,
                answer,
                f"组合数 C({total},2)={total}×{total - 1}÷2={ways}种。",
                "xingce-shuliang-yunsuan",
                "数学运算",
                [3, 4, 4][index % 3],
                module="数量关系",
            )
        )

    sequences = [
        ("2，4，8，16，（ ）", 32, "后一项是前一项的 2 倍。"),
        ("1，4，9，16，（ ）", 25, "依次为 1²、2²、3²、4²，下一项是 5²。"),
        ("3，6，11，18，（ ）", 27, "相邻两项之差为 3、5、7、9。"),
        ("2，3，5，8，13，（ ）", 21, "从第三项起，每项等于前两项之和。"),
    ]
    for index, (sequence, value, explanation) in enumerate(sequences, 1):
        options, answer = _numeric_options(value, 3, index + 1)
        questions.append(
            _question(
                f"seed-shuliang-shulie-{index:02d}",
                f"数列：{sequence}，括号处应填：",
                options,
                answer,
                explanation,
                "xingce-shuliang-shuzi",
                "数字推理",
                [2, 3, 3, 4][index % 4],
                module="数量关系",
            )
        )
    return questions


def _panduan_questions() -> list[dict]:
    questions: list[dict] = []

    definitions = [
        (
            "沉没成本是指已经发生且无法收回的成本。下列属于沉没成本的是：",
            "已支付且不可退还的定金",
            ["未来计划投入的广告费", "可以全额退还的押金", "尚未签订的采购合同金额"],
            "定金已支付且不可退，属于无法收回的沉没成本。",
            "xingce-panduan-dingyi",
            "定义判断",
        ),
        (
            (
                "光环效应是指人们对他人的某一特征形成好印象后，会据此推断其他方面也很好。"
                "下列体现光环效应的是："
            ),
            "因为某演员外形出众，就认为他演技也很好",
            ["因为某员工迟到，就扣发其绩效", "根据考试成绩评价学生", "通过面试了解应聘者能力"],
            "由外形好推断演技好，是以局部印象推断整体。",
            "xingce-panduan-dingyi",
            "定义判断",
        ),
        (
            (
                "机会成本是指为了得到某种东西而放弃的其他选择中价值最高的那一个。"
                "下列属于机会成本的是："
            ),
            "放弃工作去读研而少挣的工资",
            ["读研期间支付的学费", "购买教材的费用", "往返学校的交通费"],
            "放弃工作少挣的工资，是选择读研所放弃的最大收益。",
            "xingce-panduan-dingyi",
            "定义判断",
        ),
        (
            (
                "从众效应是指个体在群体压力下改变自己的意见，与多数人保持一致。"
                "下列体现从众效应的是："
            ),
            "小组讨论时，原本有不同意见的小李最终附和大家",
            ["小王坚持自己的判断并说服了同事", "小张独立完成调研报告", "小赵拒绝参加集体活动"],
            "小李在群体压力下改变意见，符合从众效应。",
            "xingce-panduan-dingyi",
            "定义判断",
        ),
    ]
    for index, (stem, correct, distractors, explanation, kp, name) in enumerate(
        definitions, 1
    ):
        options, answer = _text_options(correct, distractors, index)
        questions.append(
            _question(
                f"seed-panduan-dingyi-{index:02d}",
                stem,
                options,
                answer,
                explanation,
                kp,
                name,
                [2, 3, 3, 4][index % 4],
                module="判断推理",
            )
        )

    analogies = [
        (
            "医生：医院",
            "教师：学校",
            ["学生：书本", "厨师：菜肴", "司机：汽车"],
            "职业与其主要工作场所的对应关系。",
        ),
        (
            "铅笔：写字",
            "扫帚：扫地",
            ["书本：阅读", "汽车：道路", "水杯：玻璃"],
            "工具与其主要功能的对应关系。",
        ),
        (
            "书籍：知识",
            "食物：营养",
            ["电脑：网络", "衣服：商店", "音乐：乐器"],
            "载体与其所承载内容的对应关系。",
        ),
        (
            "熊猫：中国",
            "袋鼠：澳大利亚",
            ["老虎：森林", "企鹅：南极", "鲸鱼：海洋"],
            "动物与其代表性国家的对应关系。",
        ),
    ]
    for index, (stem, correct, distractors, explanation) in enumerate(
        analogies, 1
    ):
        options, answer = _text_options(correct, distractors, index + 1)
        questions.append(
            _question(
                f"seed-panduan-leibi-{index:02d}",
                f"{stem}\n\n下列选项中与题干逻辑关系最为相似的是：",
                options,
                answer,
                explanation,
                "xingce-panduan-leibi",
                "类比推理",
                [2, 3, 3, 4][index % 4],
                module="判断推理",
            )
        )

    logic = [
        (
            "所有参加培训的员工都通过了考核。小王通过了考核。由此可以推出：",
            "小王可能参加了培训",
            ["小王一定参加了培训", "小王一定没有参加培训", "培训对考核没有任何作用"],
            "肯定后件不能必然肯定前件，只能推出“可能”。",
            "xingce-panduan-luoji",
            "逻辑判断",
        ),
        (
            "只有年满 18 周岁，才有选举权。小李有选举权。由此可以推出：",
            "小李已年满 18 周岁",
            ["小李一定未满 18 周岁", "年满 18 周岁的人都有选举权", "小李参加了本次选举"],
            "“只有 A 才 B”中，B 成立可推出 A 成立。",
            "xingce-panduan-luoji",
            "逻辑判断",
        ),
        (
            (
                "某公司为员工提供免费咖啡后，员工效率明显提高，因此咖啡能提高效率。"
                "以下最能削弱该结论的是："
            ),
            "该公司同期还改善了办公环境并调整了绩效考核",
            ["部分员工并不喜欢喝咖啡", "咖啡的价格有所上涨", "员工普遍希望保留免费咖啡"],
            "存在其他同时发生的变化，不能把效率提高单独归因于咖啡。",
            "xingce-panduan-luoji",
            "逻辑判断",
        ),
        (
            "经常运动的人更少生病，因此运动能增强免疫力。以下最能加强该结论的是：",
            "运动能促进免疫细胞活性，提高机体抵抗力",
            ["有些运动员也会生病", "不运动的人也可能很健康", "运动需要长期坚持"],
            "提供运动增强免疫力的机制，直接支持结论。",
            "xingce-panduan-luoji",
            "逻辑判断",
        ),
    ]
    for index, (stem, correct, distractors, explanation, kp, name) in enumerate(
        logic, 1
    ):
        options, answer = _text_options(correct, distractors, index + 2)
        questions.append(
            _question(
                f"seed-panduan-luoji-{index:02d}",
                stem,
                options,
                answer,
                explanation,
                kp,
                name,
                [3, 3, 4, 4][index % 4],
                module="判断推理",
            )
        )
    return questions


def _changshi_questions() -> list[dict]:
    items = [
        (
            "我国的根本政治制度是：",
            "人民代表大会制度",
            ["中国共产党领导的多党合作和政治协商制度", "民族区域自治制度", "基层群众自治制度"],
            "人民代表大会制度是我国的根本政治制度。",
            "xingce-changshi-zhengzhi",
            "政治常识",
        ),
        (
            "中国共产党的根本宗旨是：",
            "全心全意为人民服务",
            ["实现共同富裕", "坚持改革开放", "建设现代化强国"],
            "党的根本宗旨是全心全意为人民服务。",
            "xingce-changshi-zhengzhi",
            "政治常识",
        ),
        (
            "新发展理念的内容是：",
            "创新、协调、绿色、开放、共享",
            ["改革、发展、稳定、和谐、共赢", "富强、民主、文明、和谐、美丽", "自由、平等、公正、法治、诚信"],
            "新发展理念为创新、协调、绿色、开放、共享。",
            "xingce-changshi-zhengzhi",
            "政治常识",
        ),
        (
            "下列属于我国公民基本权利的是：",
            "选举权与被选举权",
            ["依法纳税", "服兵役", "遵守宪法和法律"],
            "选举权与被选举权属于公民基本权利，其余为义务。",
            "xingce-changshi-falv",
            "法律常识",
        ),
        (
            "民事主体从事民事活动，应当秉持诚实、恪守承诺。这体现的是：",
            "诚信原则",
            ["自愿原则", "公平原则", "绿色原则"],
            "诚实守信、恪守承诺对应民法典的诚信原则。",
            "xingce-changshi-falv",
            "法律常识",
        ),
        (
            "下列属于行政处罚的是：",
            "罚款",
            ["罚金", "赔偿损失", "拘役"],
            "罚款是行政处罚；罚金、拘役是刑罚，赔偿损失是民事责任。",
            "xingce-changshi-falv",
            "法律常识",
        ),
        (
            "通货膨胀较为严重时，通常宜采取的货币政策是：",
            "紧缩性货币政策",
            ["扩张性货币政策", "降低存款准备金率", "大规模增加货币供应"],
            "抑制通胀应收紧货币供应，采取紧缩性货币政策。",
            "xingce-changshi-jingji",
            "经济常识",
        ),
        (
            "国内生产总值（GDP）衡量的是一国：",
            "一定时期内境内生产的最终产品和服务的价值",
            ["居民储蓄总额", "财政收入总额", "进出口总额"],
            "GDP 核算的是境内最终产品和服务的市场价值。",
            "xingce-changshi-jingji",
            "经济常识",
        ),
        (
            "在社会主义市场经济中，市场在资源配置中起：",
            "决定性作用",
            ["基础性作用", "辅助性作用", "补充性作用"],
            "党的十八届三中全会提出市场在资源配置中起决定性作用。",
            "xingce-changshi-jingji",
            "经济常识",
        ),
    ]
    questions: list[dict] = []
    for index, (stem, correct, distractors, explanation, kp, name) in enumerate(
        items, 1
    ):
        options, answer = _text_options(correct, distractors, index)
        questions.append(
            _question(
                f"seed-changshi-{index:02d}",
                stem,
                options,
                answer,
                explanation,
                kp,
                name,
                [2, 3, 3, 4][index % 4],
                module="常识判断",
            )
        )
    return questions


def _shenlun_questions() -> list[dict]:
    return [
        _short(
            "seed-shenlun-guina-01",
            "请根据给定材料，概括基层治理中存在的主要问题。"
            "要求：全面、准确、分条作答，不超过 200 字。",
            "基层治理存在力量不足、职责不清、群众参与度低、数字化手段使用不充分等问题。",
            [
                {"point": "治理力量不足", "keywords": ["力量", "人手", "人员"], "score": 2},
                {"point": "职责边界不清", "keywords": ["职责", "边界", "推诿"], "score": 2},
                {"point": "群众参与不足", "keywords": ["群众", "参与"], "score": 2},
                {"point": "数字化手段不足", "keywords": ["数字", "信息化", "手段"], "score": 2},
            ],
            "shenlun-guina",
            "归纳概括",
            subject="申论",
            module="归纳概括",
        ),
        _short(
            "seed-shenlun-fenxi-01",
            "请谈谈对“绿水青山就是金山银山”的理解。要求：观点明确，分析深入，不超过 300 字。",
            "绿水青山是生态优势，保护生态就是保护生产力；把生态优势转化为经济优势，"
            "实现生态保护与经济发展的统一。",
            [
                {"point": "生态本身就是财富", "keywords": ["生态", "绿水青山", "财富"], "score": 2},
                {"point": "保护生态就是发展生产力", "keywords": ["保护", "生产力"], "score": 2},
                {"point": "生态优势转化为经济优势", "keywords": ["转化", "经济", "优势"], "score": 2},
                {"point": "二者辩证统一", "keywords": ["统一", "协调", "兼顾"], "score": 2},
            ],
            "shenlun-fenxi",
            "综合分析",
            subject="申论",
            module="综合分析",
        ),
        _short(
            "seed-shenlun-duice-01",
            "针对材料反映的农村电商发展问题，提出三条对策。要求：针对性强、切实可行，不超过 250 字。",
            "完善农村物流网络；加强电商人才培训；打造特色农产品品牌；加大金融和基础设施支持。",
            [
                {"point": "完善物流网络", "keywords": ["物流", "配送", "冷链"], "score": 2},
                {"point": "培训电商人才", "keywords": ["培训", "人才", "技能"], "score": 2},
                {"point": "打造特色品牌", "keywords": ["品牌", "特色", "标准化"], "score": 2},
                {"point": "加大资金与基础设施支持", "keywords": ["资金", "金融", "基础设施"], "score": 2},
            ],
            "shenlun-duice",
            "提出对策",
            subject="申论",
            module="提出对策",
        ),
        _short(
            "seed-shenlun-zuowen-01",
            "以“基层治理的力度与温度”为主题，自选角度，自拟标题，写一篇文章。"
            "要求：观点明确，结构完整，论证充分，不少于 800 字。",
            "既坚持依法治理、严格执法，又注重人文关怀、柔性服务，实现刚性与柔性的统一。",
            [
                {"point": "点明力度与温度的关系", "keywords": ["力度", "温度", "统一"], "score": 2},
                {"point": "力度体现为依法治理", "keywords": ["依法", "法治", "规范"], "score": 2},
                {"point": "温度体现为以人为本", "keywords": ["以人为本", "群众", "服务"], "score": 2},
                {"point": "二者结合的具体路径", "keywords": ["结合", "刚柔", "机制"], "score": 2},
            ],
            "shenlun-zuowen",
            "文章写作",
            subject="申论",
            module="文章写作",
            difficulty=4,
        ),
    ]


def build_question_bank() -> list[dict]:
    questions: list[dict] = []

    for i in range(1, 7):
        base = 1000 + i * 137
        growth = 80 + i * 23
        current = base + growth
        rate = growth / base * 100
        options, answer = _numeric_options(rate, 1.2, i, "%")
        questions.append(
            _question(
                f"seed-ziliao-growth-{i:02d}",
                f"某地区2024年生产总值为{base}亿元，2025年为{current}亿元。2025年生产总值同比增长率约为：",
                options,
                answer,
                f"增长率=(现期-基期)÷基期=({current}-{base})÷{base}≈{rate:.1f}%。",
                "xingce-ziliao-zengzhang",
                "增长率",
                [2, 3, 3, 4][i % 4],
            )
        )

    for i in range(1, 7):
        total = 2000 + i * 211
        part = 600 + i * 73
        percent = part / total * 100
        options, answer = _numeric_options(percent, 1.5, i + 1, "%")
        questions.append(
            _question(
                f"seed-ziliao-ratio-{i:02d}",
                f"某市2025年一般公共预算收入为{total}亿元，其中税收收入为{part}亿元。税收收入占一般公共预算收入的比重约为：",
                options,
                answer,
                f"比重=部分÷整体={part}÷{total}≈{percent:.1f}%。",
                "xingce-ziliao-bizhong",
                "比重",
                [2, 3, 3, 4][i % 4],
            )
        )

    for i in range(1, 7):
        total = 1200 + i * 97
        count = 150 + i * 13
        average = total / count
        options, answer = _numeric_options(average, 1.0, i + 2, "万吨")
        questions.append(
            _question(
                f"seed-ziliao-average-{i:02d}",
                f"某企业全年产量为{total}万吨，共有{count}个车间。平均每个车间的产量约为：",
                options,
                answer,
                f"平均数=总量÷份数={total}÷{count}≈{average:.1f}万吨。",
                "xingce-ziliao-pingjun",
                "平均数",
                [2, 3, 3, 4][i % 4],
            )
        )

    for i in range(1, 7):
        current = 800 + i * 53
        previous = 200 + i * 17
        ratio = current / previous
        options, answer = _numeric_options(ratio, 0.4, i + 3, "倍")
        questions.append(
            _question(
                f"seed-ziliao-multiple-{i:02d}",
                f"某公司2025年营业收入为{current}万元，2024年为{previous}万元。2025年营业收入是2024年的多少倍？",
                options,
                answer,
                f"倍数=A÷B={current}÷{previous}≈{ratio:.1f}倍。",
                "xingce-ziliao-beishu",
                "倍数",
                [2, 3, 3, 4][i % 4],
            )
        )

    for i in range(1, 7):
        current = 1500 + i * 130
        rate = 8 + i
        base = current / (1 + rate / 100)
        options, answer = _numeric_options(base, 50, i, "亿元")
        questions.append(
            _question(
                f"seed-ziliao-base-{i:02d}",
                f"某地区2025年生产总值为{current}亿元，同比增长率为{rate}%。2024年生产总值约为：",
                options,
                answer,
                f"基期=现期÷(1+增长率)={current}÷(1+{rate}%)≈{base:.1f}亿元。",
                "xingce-ziliao-zengzhang",
                "增长率",
                [2, 3, 3, 4][i % 4],
            )
        )

    for i in range(1, 7):
        numerator = 4832 + i * 137
        denominator = 1276 + i * 29
        value = numerator / denominator
        options, answer = _numeric_options(value, 0.3, i + 1)
        questions.append(
            _question(
                f"seed-ziliao-estimate-{i:02d}",
                f"估算 {numerator}÷{denominator} 的结果，最接近：",
                options,
                answer,
                f"把分母截取前三位，分子同比截位后直接相除，结果约为{value:.1f}。",
                "xingce-ziliao-susuan",
                "速算技巧",
                [2, 3, 3, 4][i % 4],
            )
        )

    questions.extend(
        [
            _short(
                "seed-ziliao-short-01",
                "简述资料分析中截位直除的步骤，并说明截位时要注意什么。",
                "先看选项差距；选项差距大可以截位，差距小保留更多有效数字。截位直除时分母截前三位、分子按同比例截位，再直接相除；分子分母截位方向要一致。",
                [
                    {
                        "point": "先看选项差距",
                        "keywords": ["选项差距", "差距"],
                        "score": 2,
                    },
                    {
                        "point": "分母截前三位、分子同比截位",
                        "keywords": ["分母", "前三位", "分子", "同比例", "截位"],
                        "score": 2,
                    },
                    {
                        "point": "截位方向一致",
                        "keywords": ["方向", "一致"],
                        "score": 2,
                    },
                    {
                        "point": "选项差距小保留更多有效数字",
                        "keywords": ["有效数字", "保留"],
                        "score": 2,
                    },
                ],
                "xingce-ziliao-susuan",
                "速算技巧",
            ),
            _short(
                "seed-ziliao-short-02",
                "说明增长率、基期、增长量之间的关系，并写出基期公式。",
                "增长率=(现期-基期)÷基期；基期=现期÷(1+增长率)；增长量=现期-基期。隔年增长率=r1+r2+r1×r2；混合增长率介于两部分之间。",
                [
                    {
                        "point": "增长率公式",
                        "keywords": ["增长率", "现期", "基期"],
                        "score": 2,
                    },
                    {
                        "point": "基期公式",
                        "keywords": ["基期", "现期", "1+增长率", "1+r"],
                        "score": 3,
                    },
                    {
                        "point": "增长量公式",
                        "keywords": ["增长量", "现期", "基期"],
                        "score": 2,
                    },
                    {
                        "point": "隔年或混合增长",
                        "keywords": ["隔年", "混合", "r1", "r2"],
                        "score": 1,
                    },
                ],
                "xingce-ziliao-zengzhang",
                "增长率",
            ),
        ]
    )

    questions.extend(_yanyu_questions())
    questions.extend(_shuliang_questions())
    questions.extend(_panduan_questions())
    questions.extend(_changshi_questions())
    questions.extend(_shenlun_questions())
    return questions


async def seed_question_bank(db: AsyncSession) -> None:
    result = await db.execute(select(Question.id))
    existing_ids = set(result.scalars())
    inserted = False
    for item in build_question_bank():
        if item["id"] in existing_ids:
            continue
        db.add(Question(**item))
        inserted = True
    if inserted:
        await db.commit()
