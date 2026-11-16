"""Local demo model used when MOCK_LLM=1.

It lets the full UI, session persistence, transfer flow, ingestion and
retrieval be exercised without an external LLM key.
"""

import re
from collections.abc import AsyncGenerator
from datetime import date

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

_QUOTED_MARKERS = (
    "For context: below is a transcript",
    "tool returned result",
    "<<<BEGIN_QUOTED_AGENT_CONTENT>>>",
)
_STATUS_LABELS = {
    "ready": "已就绪",
    "processing": "入库中",
    "pending": "等待中",
    "failed": "失败",
}


def _agent_name(request: LlmRequest) -> str:
    instruction = str(request.config.system_instruction or "")
    match = re.search(r'internal name is "([^"]+)"', instruction)
    return match.group(1) if match else "counselor"


def _last_user_text(request: LlmRequest) -> str:
    for content in reversed(request.contents):
        if content.role != "user":
            continue
        for part in content.parts or []:
            text = getattr(part, "text", None)
            if text and not any(marker in text for marker in _QUOTED_MARKERS):
                return text
    return ""


def _last_function_response(request: LlmRequest) -> tuple[str, dict] | None:
    for content in reversed(request.contents):
        for part in content.parts or []:
            response = getattr(part, "function_response", None)
            if response is None:
                continue
            name = getattr(response, "name", "") or ""
            data = getattr(response, "response", None) or {}
            if isinstance(data, dict) and isinstance(data.get("result"), dict):
                data = data["result"]
            return name, data if isinstance(data, dict) else {}
    return None


def _extract_url(text: str) -> str:
    match = re.search(r"https?://[^\s<>'\"]+", text)
    return match.group(0) if match else ""


def _guess_kp_id(text: str) -> str:
    if "速算" in text or "截位" in text:
        return "xingce-ziliao-susuan"
    if "增长率" in text or "基期" in text:
        return "xingce-ziliao-zengzhang"
    if "比重" in text:
        return "xingce-ziliao-bizhong"
    if "图形推理" in text:
        return "xingce-panduan-tuxing"
    if "逻辑判断" in text:
        return "xingce-panduan-luoji"
    if "逻辑填空" in text:
        return "xingce-yanyu-luoji"
    if "归纳" in text or "概括" in text:
        return "shenlun-guina"
    if "作文" in text or "文章写作" in text:
        return "shenlun-zuowen"
    return ""


class MockLlm(BaseLlm):
    """Deterministic model that exercises the agent topology."""

    model: str = "mock-demo"

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        agent = _agent_name(llm_request)
        user_text = _last_user_text(llm_request)
        tool_response = _last_function_response(llm_request)
        has_transfer = "transfer_to_agent" in llm_request.tools_dict

        if agent == "supervisor":
            if "辅导员" in user_text and has_transfer:
                yield self._function_call(
                    "transfer_to_agent", {"agent_name": "counselor"}
                )
                return
            if tool_response:
                name, data = tool_response
                if name == "get_study_snapshot":
                    text = self._supervisor_report(data)
                elif name == "generate_study_plan":
                    text = self._plan_answer(data)
                else:
                    text = "学情数据读取完成。"
                async for response in self._yield_text(text, stream):
                    yield response
                return
            if (
                "计划" in user_text or "安排" in user_text
            ) and "generate_study_plan" in llm_request.tools_dict:
                yield self._function_call("generate_study_plan", {})
                return
            yield self._function_call("get_study_snapshot", {})
            return

        if agent == "examiner":
            if "辅导员" in user_text and has_transfer:
                yield self._function_call(
                    "transfer_to_agent", {"agent_name": "counselor"}
                )
                return
            if tool_response and tool_response[0] == "generate_exam":
                data = tool_response[1]
                text = str(
                    data.get("message")
                    or "试卷已生成，点击卡片开始考试。交卷后改卷老师会给你报告。"
                )
                async for response in self._yield_text(text, stream):
                    yield response
                return
            yield self._function_call(
                "generate_exam",
                {
                    "subject": "行测",
                    "module": "资料分析",
                    "question_count": 30,
                    "minutes": 35,
                    "difficulty": "medium",
                },
            )
            return

        if agent == "collector":
            if tool_response:
                name, data = tool_response
                if name == "list_materials":
                    text = self._materials_answer(data)
                elif name == "search_materials":
                    text = self._search_answer(data)
                elif name == "import_url":
                    text = str(data.get("message") or "已提交入库任务。")
                elif name == "web_search":
                    text = self._web_answer(data)
                else:
                    text = "资料搜集完成。"
                async for response in self._yield_text(text, stream):
                    yield response
                return

            url = _extract_url(user_text)
            if url:
                yield self._function_call("import_url", {"url": url})
                return
            if "网页" in user_text or "上网" in user_text:
                yield self._function_call("web_search", {"query": user_text})
                return
            if "找资料" in user_text or "搜资料" in user_text:
                yield self._function_call("search_materials", {"query": user_text})
                return
            yield self._function_call("list_materials", {})
            return

        if agent == "organizer":
            if tool_response:
                name, data = tool_response
                if name == "list_materials":
                    materials = data.get("materials") or []
                    if "重新索引" in user_text and materials:
                        candidate = next(
                            (
                                item
                                for item in materials
                                if item.get("status") in {"ready", "failed"}
                            ),
                            materials[0],
                        )
                        yield self._function_call(
                            "reindex_material", {"material_id": candidate["id"]}
                        )
                        return
                    text = self._materials_answer(data)
                elif name == "reindex_material":
                    text = "已重新提交索引。" + str(data.get("message") or "")
                else:
                    text = "资料整理完成。"
                async for response in self._yield_text(text, stream):
                    yield response
                return

            yield self._function_call("list_materials", {})
            return

        if agent == "knowledge":
            if tool_response:
                name, data = tool_response
                if name in {"search_knowledge", "search_materials"}:
                    text = self._knowledge_answer(data)
                elif name == "list_knowledge_tree":
                    text = self._tree_answer(data)
                elif name == "get_knowledge_card":
                    text = self._card_answer(data)
                else:
                    text = "知识点整理完成。"
                async for response in self._yield_text(text, stream):
                    yield response
                return

            if "知识树" in user_text:
                yield self._function_call("list_knowledge_tree", {})
                return
            if "知识卡片" in user_text:
                kp_id = _guess_kp_id(user_text)
                if kp_id:
                    yield self._function_call(
                        "get_knowledge_card", {"kp_id": kp_id}
                    )
                    return
            yield self._function_call(
                "search_knowledge",
                {"query": user_text, "subject": "", "module": ""},
            )
            return

        if agent == "grader":
            if tool_response and tool_response[0] == "get_latest_attempt_report":
                text = self._grading_answer(tool_response[1])
                async for response in self._yield_text(text, stream):
                    yield response
                return
            yield self._function_call("get_latest_attempt_report", {})
            return

        if ("学情" in user_text or "计划" in user_text or "督导" in user_text) and has_transfer:
            yield self._function_call(
                "transfer_to_agent", {"agent_name": "supervisor"}
            )
            return
        if any(
            keyword in user_text
            for keyword in ("改卷", "错题", "为什么错", "举一反三", "得分", "成绩")
        ) and has_transfer:
            yield self._function_call(
                "transfer_to_agent", {"agent_name": "grader"}
            )
            return
        if ("出卷" in user_text or "小卷" in user_text or "考试" in user_text) and has_transfer:
            yield self._function_call(
                "transfer_to_agent", {"agent_name": "examiner"}
            )
            return
        if any(
            keyword in user_text
            for keyword in ("上传", "导入", "网页", "文件", "找资料", "搜资料", "搜索")
        ) and has_transfer:
            yield self._function_call(
                "transfer_to_agent", {"agent_name": "collector"}
            )
            return
        if any(
            keyword in user_text
            for keyword in ("资料整理", "入库", "重新索引", "索引失败")
        ) and has_transfer:
            yield self._function_call(
                "transfer_to_agent", {"agent_name": "organizer"}
            )
            return
        if any(
            keyword in user_text
            for keyword in (
                "知识点",
                "知识树",
                "知识卡片",
                "资料分析",
                "速算",
                "增长率",
                "比重",
                "平均数",
                "倍数",
                "图形推理",
                "逻辑判断",
                "逻辑填空",
                "申论",
            )
        ) and has_transfer:
            yield self._function_call(
                "transfer_to_agent", {"agent_name": "knowledge"}
            )
            return

        answer = (
            "我在。你可以直接问学习方法、考试策略，也可以让我帮你看学情、"
            "排本周计划、出小卷；资料库相关可以问我“上传资料”“导入网页”"
            "或“资料分析速算技巧有哪些”。当前是本地演示模式，配置真实 LLM "
            "后回答会更完整。"
        )
        async for response in self._yield_text(answer, stream):
            yield response

    def _function_call(self, name: str, args: dict) -> LlmResponse:
        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(function_call=types.FunctionCall(name=name, args=args))],
            ),
            partial=False,
            turn_complete=True,
        )

    async def _yield_text(
        self, text: str, stream: bool
    ) -> AsyncGenerator[LlmResponse, None]:
        if not stream:
            yield LlmResponse(
                content=types.Content(
                    role="model", parts=[types.Part.from_text(text=text)]
                ),
                partial=False,
                turn_complete=True,
            )
            return

        chunk_size = 6
        for index in range(0, len(text), chunk_size):
            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=text[index : index + chunk_size])],
                ),
                partial=True,
            )
        yield LlmResponse(
            content=types.Content(
                role="model", parts=[types.Part.from_text(text=text)]
            ),
            partial=False,
            turn_complete=True,
        )

    def _supervisor_report(self, data: dict) -> str:
        profile = data.get("profile") or {}
        name = profile.get("name", "同学")
        target = profile.get("target_exam", "国考")
        attempts = data.get("attempts", 0)
        accuracy = data.get("accuracy", 0)
        minutes = data.get("study_minutes", 0)
        coverage = data.get("coverage", 0)

        if not attempts:
            return (
                f"{name}，你当前的目标是{target}。目前还没有做题记录，"
                "所以掌握度档案还是空的。\n\n"
                "建议先做一次 30 题的资料分析诊断小卷（约 35 分钟），"
                "之后我就能按知识点给你出学情看板和学习计划。"
            )

        lines = [
            (
                f"{name}，你当前的目标是{target}。已做 {attempts} 次练习，"
                f"正确率 {accuracy}%，累计约 {minutes} 分钟，覆盖 {coverage}% 的知识点。"
            )
        ]
        weak = data.get("weak_points") or []
        if weak:
            names = "、".join(
                f"{item.get('knowledge_point_name')}（{item.get('score')}）"
                for item in weak[:3]
            )
            lines.append(f"薄弱点：{names}。")
        today_tasks = data.get("today_tasks") or []
        if today_tasks:
            lines.append(
                "今天任务："
                + "；".join(
                    str(item.get("title", "")) for item in today_tasks[:3]
                )
            )
        else:
            lines.append("今天还没有计划任务，可以让我生成本周计划。")
        alerts = data.get("alerts") or []
        if alerts:
            lines.append(
                "提醒："
                + "；".join(str(item.get("text", "")) for item in alerts[:2])
            )
        return "\n".join(lines)

    def _plan_answer(self, data: dict) -> str:
        plan = data.get("plan") or {}
        goal = plan.get("goal") or "本周计划"
        tasks = plan.get("tasks") or []
        today_str = date.today().isoformat()
        today_tasks = [task for task in tasks if task.get("date") == today_str]

        lines = [f"本周计划已生成：{goal}。"]
        if today_tasks:
            lines.append("今天：")
            for task in today_tasks[:4]:
                lines.append(
                    f"- {task.get('title')}（{task.get('minutes')} 分钟）"
                )
        else:
            days = plan.get("days") or []
            if days:
                first = days[0]
                lines.append(f"{first.get('weekday')}安排：")
                for task in (first.get("tasks") or [])[:3]:
                    lines.append(
                        f"- {task.get('title')}（{task.get('minutes')} 分钟）"
                    )
        lines.append("完成后可以在学情看板打勾，计划会按薄弱点继续调整。")
        return "\n".join(lines)

    def _materials_answer(self, data: dict) -> str:
        materials = data.get("materials") or []
        if not materials:
            return "资料库里还没有资料。可以在资料库上传文件，或让我导入一个网页链接。"
        lines = ["最近的资料："]
        for index, item in enumerate(materials[:5], 1):
            status = _STATUS_LABELS.get(
                str(item.get("status", "")), str(item.get("status", ""))
            )
            tags = " · ".join(
                part for part in (item.get("subject"), item.get("module")) if part
            )
            suffix = f"（{tags}）" if tags else ""
            error = f"；{item.get('error')}" if item.get("error") else ""
            lines.append(
                f"{index}. {item.get('title', '未命名')} — {status}，"
                f"{item.get('chunk_count', 0)} 个分块{suffix}{error}"
            )
        return "\n".join(lines)

    def _search_answer(self, data: dict) -> str:
        chunks = data.get("chunks") or []
        if not chunks:
            return str(data.get("message") or "资料库里还没有找到相关内容。")
        lines = ["我在资料库里找到这些内容："]
        for index, hit in enumerate(chunks[:4], 1):
            title = hit.get("material_title") or "资料"
            page = hit.get("page")
            cite = f"《{title}》" + (f"第 {page} 页" if page else "")
            content = str(hit.get("content", "")).replace("#", " ").replace("\n", " ")
            content = " ".join(content.split())
            lines.append(f"{index}. {content[:200]}（{cite}）")
        return "\n".join(lines)

    def _knowledge_answer(self, data: dict) -> str:
        chunks = data.get("chunks") or []
        cards = data.get("cards") or []
        if not chunks and not cards:
            return (
                "资料库里还没有找到相关内容。你可以在资料库上传一份资料，"
                "或让我先导入示例资料，再回答你。"
            )
        lines = ["根据资料库，我找到这些内容："]
        for card in cards[:2]:
            lines.append(f"- {card.get('title')}：{card.get('summary')}")
        for index, hit in enumerate(chunks[:3], 1):
            title = hit.get("material_title") or "资料"
            page = hit.get("page")
            cite = f"《{title}》" + (f"第 {page} 页" if page else "")
            content = str(hit.get("content", "")).replace("#", " ").replace("\n", " ")
            content = " ".join(content.split())
            lines.append(f"{index}. {content[:220]}（{cite}）")
        lines.append("以上结论来自资料库；如果资料不足，建议继续上传。")
        return "\n".join(lines)

    def _tree_answer(self, data: dict) -> str:
        nodes = data.get("nodes") or []
        if not nodes:
            return "知识树还没有初始化。"
        lines = ["知识树（部分）："]
        for node in nodes:
            if node.get("level", 1) <= 2:
                indent = "  " * (node.get("level", 1) - 1)
                lines.append(
                    f"{indent}- {node.get('name')}（{node.get('chunk_count', 0)} 个分块）"
                )
        return "\n".join(lines[:24])

    def _card_answer(self, data: dict) -> str:
        card = data.get("card") or {}
        if not card:
            return "没有找到这个知识点。"
        lines = [f"{card.get('title', '知识点')}：{card.get('summary', '')}"]
        if card.get("methods"):
            lines.append(f"方法：{card['methods']}")
        if card.get("traps"):
            lines.append(f"易错：{card['traps']}")
        for hit in (card.get("source_chunks") or [])[:2]:
            title = hit.get("material_title") or "资料"
            page = hit.get("page")
            cite = f"《{title}》" + (f"第 {page} 页" if page else "")
            lines.append(f"来源：{str(hit.get('content', ''))[:160]}（{cite}）")
        return "\n".join(lines)

    def _web_answer(self, data: dict) -> str:
        if data.get("status") != "success":
            return str(data.get("message") or "网页搜索暂时不可用。")
        results = data.get("results") or []
        if not results:
            return "网页搜索没有找到结果。"
        lines = ["网页搜索结果："]
        for index, item in enumerate(results[:5], 1):
            lines.append(
                f"{index}. {item.get('title', '')} — {item.get('url', '')}\n"
                f"   {str(item.get('content', ''))[:140]}"
            )
        return "\n".join(lines)

    def _grading_answer(self, data: dict) -> str:
        report = data.get("report") or {}
        if not report:
            return (
                "还没有已批改的试卷。先去考试中心做一套卷，交卷后我就能"
                "按得分点、错题和举一反三给你分析。"
            )

        score = report.get("score", 0)
        total = report.get("total_score", 0)
        percentage = report.get("percentage", 0)
        questions = report.get("questions") or []
        wrong = [item for item in questions if not item.get("is_correct")]

        lines = [f"最近一次得分：{score}/{total}（{percentage}%）。"]
        if not wrong:
            lines.append("这次没有错题，继续保持。")
            return "\n".join(lines)

        for item in wrong[:3]:
            stem = str(item.get("stem", ""))[:80]
            lines.append(f"错题：{stem}…")
            lines.append(f"  正确答案：{item.get('correct_answer')}")
            comment = str(item.get("comment") or "")
            if comment:
                lines.append(f"  评语：{comment}")
            for variant in (item.get("variants") or [])[:2]:
                lines.append(f"  举一反三：{variant.get('stem', '')}")

        changes = report.get("mastery_changes") or []
        if changes:
            lines.append("掌握度变化：")
            for change in changes[:4]:
                lines.append(
                    f"- {change.get('knowledge_point_name')}："
                    f"{change.get('before')} → {change.get('after')}"
                )
        return "\n".join(lines)
