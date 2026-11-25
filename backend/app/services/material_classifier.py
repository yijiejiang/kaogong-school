"""判断一份资料是不是「解析篇」这类不该进题库的文本。

题本篇和解析篇是同一批题的两份 PDF。把解析篇当题目资料抽进题库，题量会翻倍，
而且解析篇里那道题的条件经常被 OCR 拆散，抽出来的题还是残的。

单看一个特征容易误判（有些题本也带「【解析】」小节），所以这里累加多个信号，
达到阈值才判定，并把命中的证据带回去，方便在页面上解释为什么跳过。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# 每个信号命中一次加多少分
SIGNAL_WEIGHTS: dict[str, int] = {
    "answer_mark": 3,  # 【参考答案】 每处
    "explain_mark": 2,  # 【实战解析】/【解析】 每处
    "annotation": 3,  # 花生批注这类逐题批注
    "type_mark": 2,  # 【题型分类】
    "answer_sentence": 1,  # 「综上，答案为 X 选项」
    "option_analysis": 1,  # 「A 选项，…… B 选项，……」
}
THRESHOLD = 40
SAMPLE_CHARS = 20000

SIGNAL_PATTERNS: dict[str, re.Pattern[str]] = {
    "answer_mark": re.compile(r"【参考答案】"),
    "explain_mark": re.compile(r"【(?:实战)?解析】"),
    "annotation": re.compile(r"花生批注"),
    "type_mark": re.compile(r"【题型分类】"),
    "answer_sentence": re.compile(r"(?:综上[^。]{0,20}|因此[^。]{0,20})答案为\s*[A-D]\s*选项"),
    "option_analysis": re.compile(r"[A-D]\s*选项[，,][^。]{4,80}。"),
}

SIGNAL_LABELS: dict[str, str] = {
    "answer_mark": "参考答案标记",
    "explain_mark": "解析段落",
    "annotation": "逐题批注",
    "type_mark": "题型分类标记",
    "answer_sentence": "答案结论句",
    "option_analysis": "逐项选项分析",
}


@dataclass
class AnswerKeyVerdict:
    is_answer_key: bool
    score: int
    hits: dict[str, int] = field(default_factory=dict)

    @property
    def reason(self) -> str:
        if not self.is_answer_key:
            return ""
        parts = [
            f"{SIGNAL_LABELS[name]} {count} 处"
            for name, count in sorted(self.hits.items(), key=lambda kv: -kv[1])
            if count
        ]
        return "、".join(parts[:3])


def detect_answer_key(texts: list[str]) -> AnswerKeyVerdict:
    """按信号累加给分，到阈值判为解析资料。

    必要条件：必须出现「参考答案」或逐题批注。有的题本每道题后面都跟一小节
    「【解析】」，光看解析段落数会误判；而解析篇一定有成体系的答案标注。
    """
    sample = "\n".join(texts)[:SAMPLE_CHARS]
    hits: dict[str, int] = {}
    score = 0
    for name, pattern in SIGNAL_PATTERNS.items():
        count = len(pattern.findall(sample))
        if not count:
            continue
        hits[name] = count
        score += count * SIGNAL_WEIGHTS[name]

    has_answer_core = hits.get("answer_mark", 0) >= 5 or hits.get(
        "annotation", 0
    ) >= 5
    return AnswerKeyVerdict(
        is_answer_key=score >= THRESHOLD and has_answer_core,
        score=score,
        hits=hits,
    )
