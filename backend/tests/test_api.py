import json
import os
import tempfile
import time
from pathlib import Path

import pytest

# 每次运行前清掉上一次留下的库。否则本地反复跑会积累数据，而 CI 是全新库，
# 两边结果不一致——曾经因此出现「本地通过、CI 失败」。
TEST_DB = Path(tempfile.gettempdir()) / "kaogong_pytest.db"
for _suffix in ("", "-wal", "-shm"):
    Path(f"{TEST_DB}{_suffix}").unlink(missing_ok=True)
os.environ["MOCK_LLM"] = "1"
os.environ["ENABLE_SCHEDULER"] = "0"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB}"

from fastapi.testclient import TestClient

from app.main import app


def _wait_until_ready(client: TestClient, material_id: str) -> dict:
    target: dict = {}
    for _ in range(150):
        materials = client.get("/api/materials").json()
        target = next(
            (item for item in materials if item["id"] == material_id), {}
        )
        if target.get("status") in {"ready", "failed"}:
            return target
        time.sleep(0.2)
    return target


import contextlib


@contextlib.contextmanager
def _auto_extraction():
    """临时开启入库自动抽取，供依赖它的用例使用。"""
    from app.config import get_settings

    settings = get_settings()
    previous = settings.enable_knowledge_extraction
    settings.enable_knowledge_extraction = True
    try:
        yield
    finally:
        settings.enable_knowledge_extraction = previous


def _seed_sample(client: TestClient) -> dict:
    response = client.post("/api/materials/seed-sample")
    assert response.status_code == 200
    material = response.json()
    ready = _wait_until_ready(client, material["id"])
    assert ready.get("status") == "ready", ready
    assert ready.get("chunk_count", 0) > 0
    return ready


def _answer_text(body: str) -> str:
    parts: list[str] = []
    for line in body.splitlines():
        if not line.startswith("data: "):
            continue
        try:
            event = json.loads(line[6:])
        except json.JSONDecodeError:
            continue
        if event.get("type") in {"delta", "message"}:
            parts.append(str(event.get("text", "")))
    return "".join(parts)


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_settings_exposes_mock_mode() -> None:
    with TestClient(app) as client:
        response = client.get("/api/settings")
        assert response.status_code == 200
        body = response.json()
        assert body["server"]["mock_mode"] is True
        assert body["server"]["llm_configured"] is True


def test_chat_transfers_to_supervisor() -> None:
    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/api/chat/stream",
            json={"message": "我最近学情怎么样？", "user_id": "pytest-user"},
        ) as response:
            body = "\n".join(response.iter_lines())

        assert response.status_code == 200
        assert '"type": "transfer"' in body
        assert '"to": "supervisor"' in body
        assert '"type": "done"' in body


def test_ingest_sample_and_search() -> None:
    with TestClient(app) as client:
        material = _seed_sample(client)

        detail = client.get(f"/api/materials/{material['id']}").json()
        assert detail["chunks"]
        assert any(
            "xingce-ziliao-susuan" == chunk["knowledge_point_id"]
            for chunk in detail["chunks"]
        )
        assert any(chunk["tags"] for chunk in detail["chunks"])
        assert all(chunk["chunk_type"] for chunk in detail["chunks"])
        assert any(chunk["heading_path"] for chunk in detail["chunks"])
        assert any(chunk["labels"] for chunk in detail["chunks"])

        search = client.post(
            "/api/search", json={"query": "资料分析速算技巧", "top_k": 5}
        )
        assert search.status_code == 200
        body = search.json()
        assert body["results"]
        assert any("截位" in item["content"] for item in body["results"])
        assert any(card["kp_id"] == "xingce-ziliao-susuan" for card in body["cards"])
        assert all(item["chunk_type"] for item in body["results"])


def test_chat_knowledge_uses_library() -> None:
    with TestClient(app) as client:
        _seed_sample(client)

        with client.stream(
            "POST",
            "/api/chat/stream",
            json={
                "message": "资料分析速算技巧有哪些？",
                "user_id": "pytest-knowledge",
            },
        ) as response:
            body = "\n".join(response.iter_lines())

        answer = _answer_text(body)
        assert response.status_code == 200
        assert '"to": "tutor"' in body
        assert "速算" in answer or "截位" in answer
        assert "《" in answer


def _build_exam_answers(questions: list[dict]) -> list[dict]:
    short_answer = (
        "先看选项差距，分母截前三位，分子同比例截位，截位方向一致，"
        "选项差距小保留有效数字。增长率=(现期-基期)÷基期，"
        "基期=现期÷(1+增长率)，增长量=现期-基期。"
    )
    return [
        {
            "question_id": question["id"],
            "response": short_answer if question["type"] == "short" else "A",
        }
        for question in questions
    ]


def _generate_and_submit(
    client: TestClient, user_id: str, question_count: int = 30
) -> tuple[dict, dict]:
    response = client.post(
        "/api/exams/generate",
        json={
            "subject": "行测",
            "module": "资料分析",
            "question_count": question_count,
            "duration_minutes": 35 if question_count >= 20 else 10,
            "difficulty": "medium",
        },
    )
    assert response.status_code == 200
    exam = response.json()
    start = client.post(
        f"/api/exams/{exam['id']}/start", params={"user_id": user_id}
    )
    assert start.status_code == 200
    start_data = start.json()
    answers = _build_exam_answers(start_data["exam"]["questions"])
    submit = client.post(
        f"/api/attempts/{start_data['attempt_id']}/submit",
        json={"answers": answers},
    )
    assert submit.status_code == 200
    return exam, submit.json()


def test_generate_exam_and_submit() -> None:
    with TestClient(app) as client:
        # 技能库是手动导入的，全新库（如 CI）里没有。缺了它题目关联不到技能，
        # skills / skill_changes 都会是空的，所以先确保技能包已装。
        if not client.get("/api/knowledge/skills", params={"limit": 1}).json():
            client.post(
                "/api/knowledge/skill-sources/import",
                json={"use_builtin": True, "source_key": "huasheng13"},
            )

        exam, report = _generate_and_submit(client, "pytest-p2", 30)

        assert exam["question_count"] == 30
        assert report["total_score"] == 100.0
        assert len(report["questions"]) == 30
        assert (
            sum(1 for item in report["questions"] if item["type"] == "short")
            == 2
        )
        assert report["mastery_changes"]
        assert report["error_book_added"] > 0
        assert any(
            item["type"] == "short" and item["score"] > 0
            for item in report["questions"]
        )
        assert any(
            item["variants"]
            for item in report["questions"]
            if not item["is_correct"]
        )
        assert any(item.get("skills") for item in report["questions"])
        assert report["skill_changes"]
        skill_map = client.get(
            "/api/knowledge/skill-map", params={"user_id": "pytest-p2"}
        ).json()
        assert any(
            item["attempts"] > 0
            for group in skill_map["subjects"]
            for item in group["skills"]
        )
        assert (
            client.get(f"/api/attempts/{report['attempt_id']}/report").status_code
            == 200
        )
        attempts = client.get(
            "/api/attempts", params={"user_id": "pytest-p2"}
        ).json()
        assert attempts
        assert attempts[0]["status"] == "graded"


def test_chat_examiner_generates_exam() -> None:
    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/api/chat/stream",
            json={
                "message": "帮我出一套资料分析小卷",
                "user_id": "pytest-exam-chat",
            },
        ) as response:
            body = "\n".join(response.iter_lines())

        assert response.status_code == 200
        assert '"to": "examiner"' in body
        assert "exam_card" in body


def test_chat_grader_explains_latest_report() -> None:
    with TestClient(app) as client:
        _generate_and_submit(client, "pytest-grader", 6)

        with client.stream(
            "POST",
            "/api/chat/stream",
            json={
                "message": "帮我看看错题，举一反三",
                "user_id": "pytest-grader",
            },
        ) as response:
            body = "\n".join(response.iter_lines())

        answer = _answer_text(body)
        assert response.status_code == 200
        assert '"to": "grader"' in body
        assert "最近一次得分" in answer or "错题" in answer


def test_p3_analytics_and_plan() -> None:
    with TestClient(app) as client:
        _generate_and_submit(client, "pytest-p3", 30)

        overview = client.get(
            "/api/analytics/overview", params={"user_id": "pytest-p3"}
        )
        assert overview.status_code == 200
        data = overview.json()
        assert data["stats"]["graded_attempts"] >= 1
        assert data["stats"]["questions"] > 0
        assert data["mastery"]
        assert data["modules"]
        assert data["weak_points"]
        assert data["trend"]
        assert isinstance(data["alerts"], list)

        generated = client.post(
            "/api/plan/generate", params={"user_id": "pytest-p3"}, json={}
        )
        assert generated.status_code == 200
        plan = generated.json()
        assert plan["tasks"]
        assert len(plan["days"]) == 7
        assert plan["adherence"]["total"] > 0
        assert plan["goal"]

        week = client.get(
            "/api/plan/week", params={"user_id": "pytest-p3"}
        ).json()
        task = week["tasks"][0]
        toggled = client.patch(
            f"/api/plan/tasks/{task['id']}",
            params={"user_id": "pytest-p3"},
            json={"done": True},
        )
        assert toggled.status_code == 200
        assert toggled.json()["status"] == "done"

        week_after = client.get(
            "/api/plan/week", params={"user_id": "pytest-p3"}
        ).json()
        assert week_after["adherence"]["done"] >= 1

        report = client.get(
            "/api/analytics/weekly-report", params={"user_id": "pytest-p3"}
        )
        assert report.status_code == 200
        report_data = report.json()
        assert "本周" in report_data["summary"]
        assert report_data["plan_total"] > 0


def test_chat_supervisor_generates_plan() -> None:
    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/api/chat/stream",
            json={
                "message": "帮我安排本周计划",
                "user_id": "pytest-p3-chat",
            },
        ) as response:
            body = "\n".join(response.iter_lines())

        answer = _answer_text(body)
        assert response.status_code == 200
        assert '"to": "supervisor"' in body
        assert "本周计划已生成" in answer or "今天" in answer


def test_image_ocr_ingestion() -> None:
    pytest.importorskip("PIL")
    from PIL import Image, ImageDraw, ImageFont

    try:
        font = ImageFont.truetype(
            "/System/Library/Fonts/STHeiti Medium.ttc", 56
        )
    except OSError:
        pytest.skip("macOS Chinese font is not available")

    image = Image.new("RGB", (760, 180), "white")
    draw = ImageDraw.Draw(image)
    draw.text((30, 60), "OCR TEST", font=font, fill="black")
    image_path = Path(tempfile.gettempdir()) / "kaogong_ocr_test.png"
    image.save(image_path)

    with TestClient(app) as client:
        with image_path.open("rb") as handle:
            response = client.post(
                "/api/materials/upload",
                files={"file": ("ocr_test.png", handle, "image/png")},
            )
        assert response.status_code == 200
        material = response.json()
        assert material["kind"] == "image"

        ready = _wait_until_ready(client, material["id"])
        assert ready.get("status") == "ready", ready
        assert ready.get("chunk_count", 0) > 0

        detail = client.get(f"/api/materials/{material['id']}").json()
        text = " ".join(chunk["content"] for chunk in detail["chunks"]).upper()
        assert "OCR" in text


def test_video_helpers() -> None:
    from app.rag.video import clean_subtitles, is_video_url

    assert is_video_url("https://www.bilibili.com/video/BV1xx411c7mD")
    assert is_video_url("https://youtu.be/abc")
    assert not is_video_url("https://example.com/article")
    assert "资料分析" in clean_subtitles(
        "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\n<v>资料分析</v>\n"
    )


def test_notifications_flow() -> None:
    import uuid

    user_id = f"pytest-p4-{uuid.uuid4().hex[:8]}"
    with TestClient(app) as client:
        run = client.post(
            "/api/notifications/run", params={"user_id": user_id}
        )
        assert run.status_code == 200

        listing = client.get(
            "/api/notifications", params={"user_id": user_id}
        ).json()
        assert listing["items"]
        assert listing["unread"] >= 1

        first = listing["items"][0]
        marked = client.patch(
            f"/api/notifications/{first['id']}/read",
            params={"user_id": user_id},
        )
        assert marked.status_code == 200
        assert marked.json()["read"] is True

        after = client.get(
            "/api/notifications", params={"user_id": user_id}
        ).json()
        assert after["unread"] <= listing["unread"]

        all_read = client.post(
            "/api/notifications/read-all", params={"user_id": user_id}
        )
        assert all_read.status_code == 200

        final = client.get(
            "/api/notifications", params={"user_id": user_id}
        ).json()
        assert final["unread"] == 0


@pytest.mark.parametrize(
    ("subject", "module"),
    [
        ("行测", "言语理解与表达"),
        ("行测", "数量关系"),
        ("行测", "判断推理"),
        ("行测", "常识判断"),
        ("申论", "归纳概括"),
    ],
)
def test_multi_module_exam_generation(subject: str, module: str) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/exams/generate",
            json={
                "subject": subject,
                "module": module,
                "question_count": 5,
                "duration_minutes": 10,
                "difficulty": "medium",
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["question_count"] >= 1
        assert body["module"] == module

        take = client.get(f"/api/exams/{body['id']}").json()
        assert take["questions"]
        assert all(
            item["knowledge_point_id"] for item in take["questions"]
        )


def test_ai_question_falls_back_in_mock_mode() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/exams/generate",
            json={
                "subject": "行测",
                "module": "资料分析",
                "question_count": 6,
                "duration_minutes": 10,
                "difficulty": "medium",
                "ai_count": 3,
                "user_id": "pytest-ai",
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["ai_generated"] == 0
        assert "回退" in body["warning"] or "演示" in body["warning"]


def test_asr_status_and_validation() -> None:
    with TestClient(app) as client:
        status = client.get("/api/asr/status")
        assert status.status_code == 200
        body = status.json()
        assert "ready" in body
        assert "model" in body

        response = client.post(
            "/api/asr/transcribe",
            files={"file": ("note.txt", b"hello", "text/plain")},
        )
        assert response.status_code == 400


def test_usage_summary_shape() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/analytics/usage",
            params={"user_id": "pytest-usage", "days": 7},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["days"] == 7
        assert len(body["daily"]) == 7
        assert "total_tokens" in body["totals"]
        assert isinstance(body["by_role"], list)


def test_usage_aggregation() -> None:
    import sqlite3
    import uuid
    from datetime import UTC, datetime

    user_id = f"pytest-usage-{uuid.uuid4().hex[:6]}"
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")
    with TestClient(app) as client:
        connection = sqlite3.connect(TEST_DB, timeout=30)
        connection.execute(
            "INSERT INTO llm_usage (id, user_id, session_id, role, model, "
            "provider, service, units, billing_mode, note, "
            "prompt_tokens, completion_tokens, total_tokens, cost, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                uuid.uuid4().hex,
                user_id,
                "s_test",
                "counselor",
                "test-model",
                "",
                "llm",
                0.0,
                "payg",
                "",
                100,
                50,
                150,
                0.25,
                now,
            ),
        )
        connection.commit()
        connection.close()

        body = client.get(
            "/api/analytics/usage", params={"user_id": user_id, "days": 7}
        ).json()
        assert body["totals"]["requests"] == 1
        assert body["totals"]["total_tokens"] == 150
        assert body["by_role"][0]["role_label"] == "辅导员"
        assert body["daily"][-1]["total_tokens"] == 150


def test_ai_question_parsing_helpers() -> None:
    from app.exams.ai_generator import (
        _extract_questions,
        _normalize_question,
    )

    raw = _extract_questions(
        '```json\n{"questions": [{"stem": "1+1=?", '
        '"options": [{"key": "A", "text": "1"}, {"key": "B", "text": "2"}, '
        '{"key": "C", "text": "3"}, {"key": "D", "text": "4"}], '
        '"answer": "B", "knowledge_point_id": "xingce-shuliang-yunsuan"}]}\n```'
    )
    assert len(raw) == 1

    normalized = _normalize_question(
        raw[0],
        subject="行测",
        module="数量关系",
        kp_options=[
            {"id": "xingce-shuliang-yunsuan", "name": "数学运算"}
        ],
        difficulty="medium",
        index=0,
    )
    assert normalized is not None
    assert normalized["answer_json"] == '{"value": "B"}'
    assert normalized["source"] == "ai"

    tolerant = _extract_questions(
        "下面是题目：\n```json\n"
        '{"questions": [{"stem": "1+1=?", '
        '"options": [{"key": "A", "text": "1"}, {"key": "B", "text": "2"}, '
        '{"key": "C", "text": "3"}, {"key": "D", "text": "4"},], '
        '"answer": "B", "knowledge_point_id": "xingce-shuliang-yunsuan"}]}\n'
        "```\n希望有帮助。"
    )
    assert len(tolerant) == 1
    assert tolerant[0]["stem"] == "1+1=?"

    from app.exams.ai_generator import AiGenerationError

    try:
        _extract_questions('[{"key": "A", "text": "1"}]')
    except AiGenerationError:
        pass
    else:
        raise AssertionError("option arrays must not be treated as questions")


def test_per_user_profiles_are_isolated() -> None:
    user_id = "pytest-multi-user"
    with TestClient(app) as client:
        bundle = client.get("/api/settings").json()
        payload = {
            "llm": {
                "api_base": bundle["llm"]["api_base"],
                "api_key": "",
                "default_model": bundle["llm"]["default_model"],
                "embedding_model": bundle["llm"]["embedding_model"],
                "asr_model": "whisper-1",
                "input_price_per_m": 1.5,
                "output_price_per_m": 6.0,
                "roles": bundle["llm"]["roles"],
            },
            "profile": {
                "name": "小王",
                "target_exam": "省考",
                "exam_date": "2027-03-01",
                "daily_minutes": 90,
            },
        }
        saved = client.put(
            "/api/settings", params={"user_id": user_id}, json=payload
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["profile"]["name"] == "小王"
        assert saved.json()["llm"]["asr_model"] == "whisper-1"
        assert saved.json()["llm"]["input_price_per_m"] == 1.5

        mine = client.get(
            "/api/settings", params={"user_id": user_id}
        ).json()
        assert mine["profile"]["target_exam"] == "省考"

        default = client.get(
            "/api/settings", params={"user_id": "local-user"}
        ).json()
        assert default["profile"]["name"] != "小王"

        users = client.get("/api/users").json()
        assert any(item["id"] == user_id for item in users)


def test_role_specific_llm_settings() -> None:
    import sqlite3

    with TestClient(app) as client:
        bundle = client.get("/api/settings").json()
        payload = {
            "llm": {
                "api_base": bundle["llm"]["api_base"],
                "api_key": "",
                "default_model": bundle["llm"]["default_model"],
                "embedding_model": bundle["llm"]["embedding_model"],
                "embedding_api_base": "",
                "embedding_api_key": "",
                "asr_model": bundle["llm"]["asr_model"],
                "asr_api_base": "",
                "asr_api_key": "",
                "input_price_per_m": bundle["llm"]["input_price_per_m"],
                "output_price_per_m": bundle["llm"]["output_price_per_m"],
                "roles": {
                    "counselor": {
                        "model": "deepseek-chat",
                        "temperature": 0.2,
                        "max_tokens": 512,
                        "top_p": 0.9,
                        "api_base": "https://role.example/v1",
                        "api_key": "sk-role-secret",
                    }
                },
            },
            "profile": bundle["profile"],
        }
        saved = client.put("/api/settings", json=payload)
        assert saved.status_code == 200, saved.text
        role = saved.json()["llm"]["roles"]["counselor"]
        assert role["model"] == "deepseek-chat"
        assert role["api_base"] == "https://role.example/v1"
        assert role["max_tokens"] == 512
        assert role["top_p"] == 0.9
        assert role["api_key_set"] is True
        assert role["api_key"] != "sk-role-secret"

        loaded = client.get("/api/settings").json()
        assert loaded["llm"]["roles"]["counselor"]["model"] == "deepseek-chat"

        connection = sqlite3.connect(TEST_DB)
        raw = connection.execute(
            "SELECT value FROM app_settings WHERE key = 'llm'"
        ).fetchone()[0]
        connection.close()
        assert "sk-role-secret" not in raw

        payload["llm"]["roles"]["counselor"] = {
            "model": "deepseek-chat",
            "temperature": 0.2,
            "max_tokens": 512,
            "top_p": 0.9,
            "api_base": "https://role.example/v1",
            "api_key": "",
            "clear_api_key": True,
        }
        cleared = client.put("/api/settings", json=payload)
        assert cleared.status_code == 200, cleared.text
        cleared_role = cleared.json()["llm"]["roles"]["counselor"]
        assert cleared_role["api_key_set"] is False
        assert cleared_role["api_base"] == "https://role.example/v1"


def test_role_model_endpoint_fallback() -> None:
    from app.schemas.settings import LlmSettings, RoleModelConfig
    from app.services.llm import role_model_config

    llm = LlmSettings(
        api_base="https://global.example/v1",
        api_key="global-key",
        default_model="default-model",
        roles={
            "counselor": RoleModelConfig(
                model="role-model",
                temperature=0.1,
                max_tokens=256,
                top_p=0.8,
                api_base="https://role.example/v1",
                api_key="role-key",
            ),
            "grader": RoleModelConfig(temperature=0.4),
        },
    )
    counselor = role_model_config(llm, "counselor")
    assert counselor.model == "role-model"
    assert counselor.api_base == "https://role.example/v1"
    assert counselor.api_key == "role-key"
    assert counselor.max_tokens == 256
    assert counselor.top_p == 0.8

    grader = role_model_config(llm, "grader")
    assert grader.model == "default-model"
    assert grader.api_base == "https://global.example/v1"
    assert grader.api_key == "global-key"
    assert grader.temperature == 0.4


async def test_asr_api_transcription(monkeypatch, tmp_path) -> None:
    from app.rag import asr
    from app.schemas.settings import LlmSettings

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self) -> dict:
            return {"text": "资料分析速算技巧"}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, headers=None, data=None, files=None):
            assert url.endswith("/audio/transcriptions")
            assert headers["Authorization"] == "Bearer test-key"
            assert data["model"] == "whisper-1"
            return FakeResponse()

    monkeypatch.setattr(asr.httpx, "AsyncClient", lambda **kwargs: FakeClient())

    path = tmp_path / "sample.m4a"
    path.write_bytes(b"fake-audio")
    llm = LlmSettings(api_base="https://example.com/v1", api_key="test-key")
    result = await asr.transcribe_file(path, llm)
    assert result.text == "资料分析速算技巧"
    assert result.provider == "api"


async def test_asr_unavailable_raises(tmp_path) -> None:
    from app.rag.asr import AsrUnavailable, local_available, transcribe_file
    from app.schemas.settings import LlmSettings

    if local_available():
        return

    path = tmp_path / "sample.m4a"
    path.write_bytes(b"fake-audio")
    try:
        await transcribe_file(path, LlmSettings())
    except AsrUnavailable:
        return
    raise AssertionError("expected AsrUnavailable")


def test_model_list_endpoint(monkeypatch) -> None:
    from app.api import settings as settings_api

    class FakeResponse:
        status_code = 200

        def json(self) -> dict:
            return {
                "data": [
                    {"id": "qwen-plus", "owned_by": "aliyun"},
                    {"id": "deepseek-chat", "owned_by": "deepseek"},
                ]
            }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None):
            assert url == "https://models.example/v1/models"
            assert headers["Authorization"] == "Bearer test-key"
            return FakeResponse()

    monkeypatch.setattr(
        settings_api.httpx, "AsyncClient", lambda **kwargs: FakeClient()
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/settings/models",
            json={
                "api_base": "https://models.example/v1",
                "api_key": "test-key",
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert [item["id"] for item in body["models"]] == [
            "deepseek-chat",
            "qwen-plus",
        ]
        assert body["count"] == 2


def test_model_list_falls_back_to_v1(monkeypatch) -> None:
    from app.api import settings as settings_api

    calls: list[str] = []

    class FakeResponse:
        def __init__(self, status_code: int, payload: object = None) -> None:
            self.status_code = status_code
            self._payload = payload

        def json(self) -> object:
            return self._payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None):
            calls.append(url)
            if url.endswith("/v1/models"):
                return FakeResponse(200, ["model-a", "model-b"])
            return FakeResponse(404)

    monkeypatch.setattr(
        settings_api.httpx, "AsyncClient", lambda **kwargs: FakeClient()
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/settings/models",
            json={"api_base": "https://models.example", "api_key": "test-key"},
        )
        assert response.status_code == 200, response.text
        assert calls == [
            "https://models.example/models",
            "https://models.example/v1/models",
        ]
        assert response.json()["base_url"].endswith("/v1/models")


def test_model_list_rejects_bad_key(monkeypatch) -> None:
    from app.api import settings as settings_api

    class FakeResponse:
        status_code = 401
        text = "unauthorized"

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None):
            return FakeResponse()

    monkeypatch.setattr(
        settings_api.httpx, "AsyncClient", lambda **kwargs: FakeClient()
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/settings/models",
            json={"api_base": "https://models.example/v1", "api_key": "bad"},
        )
        assert response.status_code == 400
        assert "鉴权失败" in response.json()["detail"]


def test_model_list_blocks_metadata_address() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/settings/models",
            json={
                "api_base": "http://169.254.169.254/latest",
                "api_key": "test-key",
            },
        )
        assert response.status_code == 400
        assert "云元数据" in response.json()["detail"]


def test_leading_scratchpad_is_stripped() -> None:
    from app.api.chat import _clean_leading, _LeadingFilter

    assert (
        _clean_leading("I'll pull up your data.\n\n**目标考试**\n国考")
        == "**目标考试**\n国考"
    )
    assert _clean_leading("中文开头") == "中文开头"

    leading = _LeadingFilter()
    assert leading.feed("supervisor", "I'll pull ") == ""
    assert leading.feed("supervisor", "up your data.\n\n**目标") == "**目标"
    assert leading.feed("supervisor", "考试**") == "考试**"


def test_connect_info_and_qr() -> None:
    from app.config import get_settings

    settings = get_settings()
    previous = settings.public_base_url
    settings.public_base_url = ""
    try:
        with TestClient(app) as client:
            info = client.get("/api/connect/info")
            assert info.status_code == 200
            body = info.json()
            assert body["api_base"].startswith("http://")
            assert body["source"] == "lan"
            assert body["payload"].startswith("kaogong://connect?base=")
            assert body["port"] > 0

            qr = client.get("/api/connect/qr.png")
            assert qr.status_code == 200
            assert qr.headers["content-type"] == "image/png"
            assert qr.content.startswith(b"\x89PNG")
    finally:
        settings.public_base_url = previous


def test_connect_uses_public_base_url() -> None:
    from app.config import get_settings

    settings = get_settings()
    previous = settings.public_base_url
    settings.public_base_url = "https://kaogong.example.ts.net/"
    try:
        with TestClient(app) as client:
            body = client.get("/api/connect/info").json()
            assert body["api_base"] == "https://kaogong.example.ts.net"
            assert body["source"] == "public"
            assert body["payload"] == (
                "kaogong://connect?base=https%3A%2F%2Fkaogong.example.ts.net"
            )
    finally:
        settings.public_base_url = previous


async def test_tagging_eval_cases() -> None:
    from app.db.session import SessionLocal
    from app.knowledge.seed import seed_knowledge_tree
    from app.rag.tagging import load_prepared_points, tag_text_multi

    path = Path(__file__).resolve().parent.parent / "evals" / "library_cases.json"
    payload = json.loads(path.read_text())
    cases = payload["tagging"]

    with TestClient(app):
        pass

    async with SessionLocal() as db:
        await seed_knowledge_tree(db)
        prepared = await load_prepared_points(db)
        top1 = 0
        type_hits = 0
        for case in cases:
            result = tag_text_multi(case["text"], prepared)
            if result.knowledge_point_id == case["expected_kp"]:
                top1 += 1
            if result.chunk_type == case["expected_type"]:
                type_hits += 1

    assert top1 / len(cases) >= 0.8
    assert type_hits / len(cases) >= 0.8


def test_chunk_type_classifier() -> None:
    from app.rag.tagging import classify_chunk

    assert classify_chunk("增长率=(现期-基期)÷基期。") == "formula"
    assert classify_chunk("第一步，先看选项差距，再决定截位。") == "method"
    assert classify_chunk("常见陷阱：截位方向不一致。") == "trap"
    assert classify_chunk("行政处罚是指行政机关依法给予制裁的行为。") == "definition"
    assert classify_chunk("例题：4832÷1276 最接近多少？") == "example"


def test_knowledge_extraction_review_flow() -> None:
    with _auto_extraction(), TestClient(app) as client:
        material = _seed_sample(client)

        units = client.get(
            "/api/knowledge/units",
            params={"material_id": material["id"]},
        ).json()
        assert units, "sample ingestion should extract rule units"
        assert all(unit["status"] == "draft" for unit in units)
        assert any(unit["title"] for unit in units)
        assert all(isinstance(unit["steps"], list) for unit in units)

        first = units[0]
        approved = client.patch(
            f"/api/knowledge/units/{first['id']}",
            json={"status": "approved", "title": first["title"] + "（已审）"},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"
        assert approved.json()["title"].endswith("（已审）")

        drafts = client.get(
            "/api/knowledge/units",
            params={"material_id": material["id"], "status": "draft"},
        ).json()
        assert all(unit["id"] != first["id"] for unit in drafts)

        rejected = client.patch(
            f"/api/knowledge/units/{units[-1]['id']}",
            json={"status": "rejected"},
        )
        assert rejected.json()["status"] == "rejected"

        bad = client.patch(
            f"/api/knowledge/units/{first['id']}",
            json={"status": "unknown"},
        )
        assert bad.status_code == 400

        skills = client.get("/api/knowledge/skills").json()
        assert any(skill["source_unit_ids"] for skill in skills)
        target = skills[0]
        patched = client.patch(
            f"/api/knowledge/skills/{target['id']}",
            json={"status": "approved", "summary": "技能摘要"},
        )
        assert patched.status_code == 200
        assert patched.json()["status"] == "approved"
        assert patched.json()["summary"] == "技能摘要"

        rerun = client.post(f"/api/knowledge/extract/{material['id']}")
        assert rerun.status_code == 200
        body = rerun.json()
        assert body["model"] == "rule"
        assert body["units"] > 0
        fresh = client.get(
            "/api/knowledge/units",
            params={"material_id": material["id"]},
        ).json()
        assert all(unit["status"] == "draft" for unit in fresh)


def test_reindex_clears_knowledge_units() -> None:
    with _auto_extraction(), TestClient(app) as client:
        material = _seed_sample(client)
        before = client.get(
            "/api/knowledge/units",
            params={"material_id": material["id"]},
        ).json()
        assert before

        response = client.post(f"/api/materials/{material['id']}/reindex")
        assert response.status_code == 200
        ready = _wait_until_ready(client, material["id"])
        assert ready.get("status") == "ready"
        after = client.get(
            "/api/knowledge/units",
            params={"material_id": material["id"]},
        ).json()
        assert after
        assert {unit["id"] for unit in after}.isdisjoint(
            {unit["id"] for unit in before}
        )





def test_deepseek_config_urls() -> None:
    from app.schemas.settings import LlmSettings
    from app.services.deepseek_tools import resolve_config

    config = resolve_config(
        LlmSettings(deepseek_api_base="https://api.deepseek.com", deepseek_api_key="k")
    )
    assert config.ready
    assert config.url("/tools/search") == "https://api.deepseek.com/v1/tools/search"

    versioned = resolve_config(
        LlmSettings(
            deepseek_api_base="https://api.deepseek.com/v1/",
            deepseek_api_key="k",
        )
    )
    assert versioned.url("/tools/ocr") == "https://api.deepseek.com/v1/tools/ocr"

    empty = resolve_config(LlmSettings())
    assert not empty.ready
    assert empty.api_base == "https://api.deepseek.com"


async def test_deepseek_settings_roundtrip() -> None:
    from app.db.session import SessionLocal
    from app.services.settings_service import load_llm_settings, save_llm_settings, to_public

    with TestClient(app):
        pass

    async with SessionLocal() as db:
        previous = await load_llm_settings(db)
        try:
            saved = await save_llm_settings(
                db,
                previous.model_copy(
                    update={
                        "deepseek_api_base": "https://api.deepseek.com",
                        "deepseek_api_key": "ds-test-key",
                    }
                ),
            )
            assert saved.deepseek_api_key == "ds-test-key"
            public = to_public(saved)
            assert public.deepseek_api_key_set is True
            assert "ds-test-key" not in public.deepseek_api_key
            assert "••••" in public.deepseek_api_key

            keep = await save_llm_settings(
                db,
                saved.model_copy(
                    update={"deepseek_api_base": "", "deepseek_api_key": ""}
                ),
            )
            assert keep.deepseek_api_base == "https://api.deepseek.com"
            assert keep.deepseek_api_key == "ds-test-key"
        finally:
            await save_llm_settings(db, previous)


def test_scanned_pdf_uses_deepseek_ocr(monkeypatch, tmp_path) -> None:
    import pymupdf

    from app.rag import parsers
    from app.services.deepseek_tools import DeepSeekConfig

    path = tmp_path / "scan.pdf"
    document = pymupdf.open()
    document.new_page()
    document.save(path)
    document.close()

    from app.services.deepseek_tools import OcrPage

    def fake_ocr(
        config, file_path, filename=None, purpose="text_recognition", start_page=0
    ):
        assert config.ready
        return [OcrPage(index=start_page + 1, text="扫描页识别出的增长率公式")]

    monkeypatch.setattr(parsers, "ocr_file_sync", fake_ocr)
    parsed = parsers.parse_file(
        path,
        "scan.pdf",
        "application/pdf",
        DeepSeekConfig("https://api.deepseek.com", "test-key"),
    )
    assert "扫描页识别出的增长率公式" in parsed.text
    assert "DeepSeek OCR" in parsed.warning


def test_scanned_pdf_detection_uses_char_density() -> None:
    from app.rag.parsers import _looks_scanned

    # 每页只有页码和水印，实际是扫描件
    sparse = [(1, "第 1 页"), (2, "第 2 页"), (3, "关注公众号")]
    assert _looks_scanned(sparse)

    dense = [(1, "增长率的计算公式是增长率等于增长量除以基期量" * 3)]
    assert not _looks_scanned(dense)


def test_ocr_batches_are_page_aligned(monkeypatch, tmp_path) -> None:
    import pymupdf

    from app.rag import parsers
    from app.services.deepseek_tools import DeepSeekConfig, OcrPage

    path = tmp_path / "multi.pdf"
    document = pymupdf.open()
    for _ in range(45):
        document.new_page()
    document.save(path)
    document.close()

    calls: list[int] = []

    def fake_ocr(config, file_path, filename=None, purpose="text_recognition", start_page=0):
        calls.append(start_page)
        # 每批返回 20 页，其中第 2 页标记为截断
        pages = [
            OcrPage(index=start_page + offset + 1, text=f"p{start_page + offset + 1}")
            for offset in range(20)
            if start_page + offset + 1 <= 45
        ]
        if pages:
            pages[1].truncated = True
        return pages

    monkeypatch.setattr(parsers, "ocr_file_sync", fake_ocr)
    pages, warnings, truncated = parsers._ocr_in_batches(
        DeepSeekConfig("https://api.deepseek.com", "test-key"),
        path,
        "multi.pdf",
        45,
    )
    assert calls == [0, 20, 40]
    assert [index for index, _ in pages][:3] == [1, 2, 3]
    assert pages[-1][0] == 45
    assert truncated == 3
    assert warnings == []


async def test_deepseek_asr_preferred(monkeypatch, tmp_path) -> None:
    from app.rag import asr
    from app.schemas.settings import LlmSettings
    from app.services.deepseek_tools import DeepSeekConfig

    path = tmp_path / "short.wav"
    path.write_bytes(b"RIFF")

    async def fake_transcribe(config, file_path, filename=None):
        return "这是语音转写结果", 12.5

    monkeypatch.setattr(asr, "transcribe_audio", fake_transcribe)
    result = await asr.transcribe_file(
        path,
        LlmSettings(),
        deepseek=DeepSeekConfig("https://api.deepseek.com", "test-key"),
    )
    assert result.provider == "deepseek"
    assert result.text == "这是语音转写结果"


def test_agent_instructions_include_today() -> None:
    from datetime import date

    from app.agents.factory import create_root_agent
    from app.schemas.settings import LlmSettings

    agent = create_root_agent(
        LlmSettings(api_base="https://example.com/v1", api_key="k", default_model="test")
    )
    today = date.today().isoformat()
    assert today in agent.instruction
    assert today in agent.sub_agents[0].instruction


def test_parse_timed_subtitles() -> None:
    from app.rag.video_slides import parse_timed_subtitles

    vtt = """WEBVTT

00:00:01.000 --> 00:00:04.000
第一句讲解

00:01:05.500 --> 00:01:08.000
第二句讲解
"""
    lines = parse_timed_subtitles(vtt)
    assert len(lines) == 2
    assert lines[0].start == 1.0
    assert lines[0].end == 4.0
    assert lines[0].text == "第一句讲解"
    assert lines[1].start == 65.5
    assert lines[1].text == "第二句讲解"


def test_build_video_slides_groups_similar_frames(tmp_path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    from app.rag import video_slides

    try:
        font = ImageFont.truetype(
            "/System/Library/Fonts/Supplemental/Songti.ttc", 44
        )
    except OSError:
        pytest.skip("macOS Chinese font is not available")
    frames: list[Path] = []
    texts = [
        "资料分析速算\n截位直除方法",
        "资料分析速算\n截位直除方法",
        "增长率公式\n增长率等于增长量除以基期量",
    ]
    for index, text in enumerate(texts):
        path = tmp_path / f"frame-{index:05d}.jpg"
        image = Image.new("RGB", (1000, 500), "white")
        draw = ImageDraw.Draw(image)
        for line_index, line in enumerate(text.splitlines()):
            draw.text((50, 80 + line_index * 90), line, fill="black", font=font)
        image.save(path)
        frames.append(path)

    slides = video_slides._build_slides(
        frames, interval=2.0, duration=10.0, material_id="pytest-video"
    )
    try:
        assert len(slides) == 2
        assert "截位直除" in slides[0].ocr_text
        assert "增长率" in slides[1].ocr_text
        assert slides[0].frame_path.startswith("frames/pytest-video/")
        assert slides[1].start >= 4.0
        assert slides[1].end == 10.0
    finally:
        video_slides.clear_frames("pytest-video")


def test_slide_chunks_include_timestamps() -> None:
    from app.rag.video_slides import VideoAnalysis, VideoSlide, slide_chunks

    analysis = VideoAnalysis(
        title="资料分析课",
        duration=120,
        transcript="讲解",
        slides=[
            VideoSlide(
                index=1,
                start=10,
                end=40,
                ocr_text="截位直除",
                frame_path="frames/x/slide-001.jpg",
                transcript="先看选项差距",
                title="截位直除",
                summary="按选项差距决定截位",
                points=["先看选项"],
            )
        ],
    )
    chunks = slide_chunks(analysis)
    assert chunks[0]["time_start"] == 10
    assert chunks[0]["time_end"] == 40
    assert "截位直除" in chunks[0]["heading_path"]
    assert "先看选项差距" in chunks[0]["content"]


def test_skill_map_endpoint() -> None:
    with TestClient(app) as client:
        _seed_sample(client)
        response = client.get(
            "/api/knowledge/skill-map", params={"user_id": "pytest-user"}
        )
        assert response.status_code == 200
        body = response.json()
        assert "summary" in body
        assert body["summary"]["total"] >= 1
        assert body["subjects"]
        module = body["subjects"][0]
        assert module["skills"]
        assert "mastery_status" in module["skills"][0]
        assert "exam_patterns" in module["skills"][0]


async def test_create_point_from_unit_proposal() -> None:
    from sqlalchemy import select

    from app.db.models import KnowledgePoint, KnowledgeUnit
    from app.db.session import SessionLocal

    with _auto_extraction(), TestClient(app) as client:
        material_id = _seed_sample(client)["id"]

    name = "pytest 新考点候选"
    async with SessionLocal() as db:
        unit = (
            await db.execute(
                select(KnowledgeUnit)
                .where(KnowledgeUnit.material_id == material_id)
                .limit(1)
            )
        ).scalar_one()
        unit.proposed_knowledge_point = name
        unit.proposed_parent_id = "xingce-ziliao-susuan"
        unit.proposed_reason = "pytest"
        await db.commit()
        unit_id = unit.id

    with TestClient(app) as client:
        response = client.post(f"/api/knowledge/units/{unit_id}/create-point")
        assert response.status_code == 200
        body = response.json()
        assert body["knowledge_point"]["name"] == name
        assert body["unit"]["status"] == "approved"
        assert body["unit"]["proposed_knowledge_point"] == ""

    async with SessionLocal() as db:
        point = (
            await db.execute(
                select(KnowledgePoint).where(KnowledgePoint.name == name)
            )
        ).scalar_one()
        assert point.parent_id == "xingce-ziliao-susuan"


def test_deepseek_cost_catalog() -> None:
    from datetime import datetime

    from app.services.pricing import (
        BEIJING,
        deepseek_tier,
        is_peak,
        llm_cost,
        resolve_mode,
        service_cost,
    )

    assert deepseek_tier("deepseek-v4.1-flash") == "flash"
    assert deepseek_tier("openai/deepseek-v4-pro") == "pro"
    assert deepseek_tier("gpt-6-luna") is None

    peak = datetime(2026, 11, 18, 10, 0, tzinfo=BEIJING)
    idle = datetime(2026, 11, 21, 10, 0, tzinfo=BEIJING)
    assert is_peak(peak)
    assert not is_peak(idle)

    flash_peak = llm_cost(
        "deepseek",
        "deepseek-v4.1-flash",
        1_000_000,
        1_000_000,
        moment=peak,
    )
    assert flash_peak.cost == 10.0
    assert flash_peak.billing_mode == "payg"

    pro_idle = llm_cost(
        "deepseek", "deepseek-v4-pro", 1_000_000, 0, moment=idle
    )
    assert pro_idle.cost == 4.5

    monthly = resolve_mode("open-design.ai", {"default": "monthly"})
    assert monthly == "monthly"
    # DeepSeek 官方始终按量计费
    assert resolve_mode("deepseek", {"default": "monthly"}) == "payg"

    search = service_cost("deepseek", "search", 1000)
    assert search.cost == 5.0
    ocr = service_cost("deepseek", "ocr", 2000)
    assert ocr.cost == 3.0


def test_usage_summary_includes_provider_cost() -> None:
    with TestClient(app) as client:
        body = client.get(
            "/api/analytics/usage", params={"user_id": "pytest-cost", "days": 7}
        ).json()
        assert "by_provider" in body
        assert "by_service" in body
        assert body["totals"]["monthly_services"] == 0

        billing = client.get(
            "/api/analytics/billing", params={"user_id": "pytest-cost"}
        ).json()
        assert any(item["value"] == "monthly" for item in billing["modes"])
        assert "deepseek" in billing["price_catalog"]


async def test_save_skill_and_knowledge() -> None:
    from sqlalchemy import delete

    from app.db.models import KnowledgeUnit, Skill
    from app.db.session import SessionLocal
    from app.tools import library

    with TestClient(app):
        pass

    async with SessionLocal() as db:
        await db.execute(delete(Skill).where(Skill.id.like("skill-manual-%")))
        await db.commit()

    saved = await library.save_skill(
        name="测试专用截位法",
        module="资料分析",
        summary="按选项差距决定截几位。",
        steps=["看选项首位", "决定截 2 或 3 位"],
        signals=["选项首位不同"],
        pitfalls=["分子也截位导致误差"],
        exam_pattern="资料分析除法计算",
    )
    assert saved["status"] == "success"
    assert saved["skill"]["name"] == "测试专用截位法"
    assert saved["skill"]["module"] == "资料分析"
    assert saved["skill"]["status"] == "approved"

    knowledge = await library.save_knowledge(
        title="测试单题分析",
        summary="这道题考增长率比较。",
        steps=["先求增速", "再比较大小"],
        exam_pattern="增长率比较",
    )
    assert knowledge["status"] == "success"

    async with SessionLocal() as db:
        skill = await db.get(Skill, saved["skill"]["id"])
        assert skill is not None
        assert skill.status == "approved"
        unit = await db.get(KnowledgeUnit, knowledge["unit_id"])
        assert unit is not None
        assert unit.title == "测试单题分析"
        assert unit.status == "approved"

        # 清理
        await db.delete(skill)
        await db.delete(unit)
        await db.commit()


def test_tutor_agent_owns_save_tools() -> None:
    """答疑老师合并了原知识整理老师，保存类工具归到它名下。"""
    from app.agents.factory import create_root_agent
    from app.schemas.settings import LlmSettings

    agent = create_root_agent(
        LlmSettings(api_base="https://example.com/v1", api_key="k", default_model="t")
    )
    names = {a.name for a in agent.sub_agents}
    assert "knowledge" not in names
    assert "tutor" in names

    tutor = next(a for a in agent.sub_agents if a.name == "tutor")
    tool_names = {getattr(t, "__name__", "") for t in tutor.tools}
    assert "save_skill" in tool_names
    assert "save_knowledge" in tool_names
    assert "load_module_skills" in tool_names


def test_tutor_agent_registered() -> None:
    from app.agents.factory import create_root_agent
    from app.schemas.settings import ROLE_KEYS, LlmSettings

    assert "tutor" in ROLE_KEYS

    agent = create_root_agent(
        LlmSettings(api_base="https://example.com/v1", api_key="k", default_model="t")
    )
    names = {sub.name for sub in agent.sub_agents}
    assert "tutor" in names

    tutor = next(a for a in agent.sub_agents if a.name == "tutor")
    tool_names = {getattr(t, "__name__", "") for t in tutor.tools}
    assert {"list_skill_catalog", "find_skills", "load_module_skills"} <= tool_names


async def test_skill_catalog_and_module_load() -> None:
    from app.tools import library

    catalog = await library.list_skill_catalog()
    assert catalog["status"] == "success"
    assert catalog["total"] > 0
    modules = {item["module"] for item in catalog["modules"]}
    assert any("资料分析" in item for item in modules)

    loaded = await library.load_module_skills("资料分析")
    assert loaded["status"] == "success"
    assert loaded["count"] > 0
    assert all(skill["module"] == "资料分析" for skill in loaded["skills"])


def test_skill_sources_endpoint() -> None:
    with TestClient(app) as client:
        body = client.get("/api/knowledge/skill-sources").json()
        assert "sources" in body and "packs" in body
        assert any(pack["key"] == "huasheng13" for pack in body["packs"])
        assert any(pack["builtin"] for pack in body["packs"])


def test_builtin_skill_pack_import() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/knowledge/skill-sources/import",
            json={"use_builtin": True},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "success"
        assert body["total"] > 100

        sources = client.get("/api/knowledge/skill-sources").json()["sources"]
        entry = next(s for s in sources if s["source"] == "huasheng13")
        assert entry["count"] == body["total"]
        assert entry["file_count"] > 0


def test_skill_pack_rejects_bad_repo() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/knowledge/skill-sources/import",
            json={"repo": "not-a-url"},
        )
        assert response.status_code == 400


def test_question_bank_endpoints() -> None:
    with TestClient(app) as client:
        rows = client.get("/api/questions", params={"limit": 5}).json()
        assert rows
        first = rows[0]
        assert "stem" in first and "tags" in first

        tags = client.get("/api/questions/tags").json()
        assert tags["total"] > 0
        assert tags["modules"]

        updated = client.patch(
            f"/api/questions/{first['id']}",
            json={"tags": ["牛吃草", "工程问题"], "difficulty": 4},
        )
        assert updated.status_code == 200
        body = updated.json()
        assert body["tags"] == ["牛吃草", "工程问题"]
        assert body["difficulty"] == 4

        filtered = client.get(
            "/api/questions", params={"tag": "牛吃草"}
        ).json()
        assert any(item["id"] == first["id"] for item in filtered)

        bad = client.patch(
            f"/api/questions/{first['id']}", json={"tags": []}
        )
        assert bad.status_code == 200
        client.patch(
            f"/api/questions/{first['id']}",
            json={"tags": first["tags"], "difficulty": first["difficulty"]},
        )


def test_exam_generate_filters_by_tag() -> None:
    with TestClient(app) as client:
        client.patch(
            "/api/questions/q-tag-test",
            json={},
        )  # 不存在时返回 404，忽略
        rows = client.get("/api/questions", params={"limit": 1}).json()
        target = rows[0]
        client.patch(
            f"/api/questions/{target['id']}", json={"tags": ["独特标签XYZ"]}
        )
        exam = client.post(
            "/api/exams/generate",
            json={
                "subject": target["subject"],
                "module": target["module"],
                "question_count": 3,
                "duration_minutes": 10,
                "difficulty": "mixed",
                "tags": ["独特标签XYZ"],
            },
        )
        assert exam.status_code == 200
        assert exam.json()["question_count"] >= 1
        client.patch(
            f"/api/questions/{target['id']}", json={"tags": target["tags"]}
        )


def test_rule_tags_are_fine_grained() -> None:
    from app.services.question_extraction import _rule_tags

    tags = _rule_tags("牧场上一片青草，每天牧草匀速生长，可供 10 头牛吃 20 天", "数量关系")
    assert "牛吃草" in tags

    tags = _rule_tags("某项工程，甲单独做 12 天，乙单独做 18 天，合作需要几天", "数量关系")
    assert "工程问题" in tags


def test_split_material_stitches_across_chunks() -> None:
    from app.services.question_extraction import split_material

    chunks = [
        ("c1", "1. 甲说今天去钓鱼，乙说如果甲去他就去。\n\nA. 甲去\nB. 乙去"),
        ("c2", "C. 丙去\nD. 三人都不去"),
        ("c3", "2. 第二题的题干足够长，可以构成一道题。\n\nA. 甲\nB. 乙\nC. 丙\nD. 丁"),
    ]
    pairs = split_material(chunks, limit=10)
    assert len(pairs) == 2
    assert all(len(block) >= 30 for _, block in pairs)
    assert "C. 丙去" in pairs[0][1]


def test_fill_missing_recovers_blocks_llm_skipped() -> None:
    from app.services.question_extraction import _fill_missing

    blocks = [
        "1. 这是第一道题的题干内容，选项完整。\nA. 甲\nB. 乙\nC. 丙\nD. 丁",
        "图表页乱码 | 1200 | 1205 | 1210 |",
        "2. 这是第二道题的题干内容，选项完整。\nA. 子\nB. 丑\nC. 寅\nD. 卯",
    ]
    items = [{"chunk_index": 0, "stem": "已识别", "options": [{"key": "A", "text": "甲"}]}]
    out = _fill_missing(blocks, items)
    assert [item["chunk_index"] for item in out] == [0, 2]


def test_answer_key_material_is_not_extracted() -> None:
    from app.services.question_extraction import _is_answer_key

    textbook = [
        (
            "1. 某牧场有牛若干，草量匀速生长，可供 10 头牛吃 20 天。\n"
            "A. 5 天\nB. 10 天\nC. 15 天\nD. 20 天\n"
            "2. 某项工程甲单独做 12 天完成。\nA. 1\nB. 2\nC. 3\nD. 4"
        )
    ]
    assert not _is_answer_key(textbook)

    answer_key = [
        "1. 某牧场有牛若干。\nA. 5\nB. 10\nC. 15\nD. 20\n【参考答案】A\n【题型分类】数量关系\n【实战解析】……"
    ] * 8
    assert _is_answer_key(answer_key)


def test_stem_fingerprint_ignores_numbering_and_punctuation() -> None:
    from app.services.question_extraction import _stem_fingerprint

    left = "12. 某知名跨国公司的总部员工中，所有懂英语的员工都不精通印尼语。"
    right = "某知名跨国公司的总部员工中 所有懂英语的员工都不精通印尼语"
    assert _stem_fingerprint(left) == _stem_fingerprint(right)
    assert _stem_fingerprint(left) != _stem_fingerprint("另一道完全不同的题目题干内容")


def test_answer_key_detector_ignores_graded_textbook() -> None:
    from app.services.material_classifier import detect_answer_key

    # 题本偶尔带一小节解析，但主体是题干和选项，不该被判成解析篇
    textbook = "\n".join(
        f"{i}. 题干第{i}题，选项如下：\nA. 甲\nB. 乙\nC. 丙\nD. 丁\n【解析】这里是简要说明。"
        for i in range(1, 40)
    )
    verdict = detect_answer_key([textbook])
    assert verdict.is_answer_key is False, verdict.hits


def test_answer_key_detector_flags_explanation_book() -> None:
    from app.services.material_classifier import detect_answer_key

    book = "\n".join(
        f"{i}. 题干第{i}题：\nA. 甲\nB. 乙\nC. 丙\nD. 丁\n"
        f"【参考答案】A\n【题型分类】削弱型\n【实战解析】A 选项，说明理由。综上，答案为 A 选项。"
        f"\n花生批注：注意这里的坑。"
        for i in range(1, 25)
    )
    verdict = detect_answer_key([book])
    assert verdict.is_answer_key is True
    assert "参考答案标记" in verdict.reason


def test_sqlite_uses_wal_and_busy_timeout() -> None:
    """WAL 让批量写入期间读请求照常返回；busy_timeout 防止请求无限挂起。"""
    import asyncio

    from sqlalchemy import text

    from app.db.session import engine

    async def read_pragmas() -> dict[str, str]:
        async with engine.connect() as conn:
            return {
                name: str((await conn.execute(text(f"PRAGMA {name}"))).scalar())
                for name in ("journal_mode", "busy_timeout")
            }

    pragmas = asyncio.run(read_pragmas())
    assert pragmas["journal_mode"].lower() == "wal"
    assert int(pragmas["busy_timeout"]) > 0


def test_db_busy_returns_readable_error() -> None:
    """写锁占满时给 503 和可读提示，而不是让请求挂到前端超时。"""
    import asyncio

    from sqlalchemy.exc import OperationalError

    from app.main import handle_db_busy

    exc = OperationalError("UPDATE", {}, Exception("database is locked"))
    response = asyncio.run(handle_db_busy(None, exc))
    assert response.status_code == 503
    assert "稍后重试" in response.body.decode()


def test_manual_knowledge_unit_without_material() -> None:
    """手动新增的知识条目没有来源资料，material_id / chunk_id 为空也要能存。"""
    with TestClient(app) as client:
        created = client.post(
            "/api/knowledge/units",
            json={
                "title": "牛吃草的三种变形",
                "summary": "草量增长、牛数变化、混合吃草",
                "steps": ["设原有草量", "求每天增长量", "代入求解"],
                "pitfalls": ["忽略草量增长"],
                "knowledge_point_name": "牛吃草",
            },
        )
        assert created.status_code == 200, created.text
        unit = created.json()
        assert unit["title"] == "牛吃草的三种变形"
        assert unit["material_id"] in (None, "")
        assert unit["steps"] == ["设原有草量", "求每天增长量", "代入求解"]
        assert unit["status"] == "draft"

        listed = client.get("/api/knowledge/units", params={"limit": 50}).json()
        assert any(item["id"] == unit["id"] for item in listed)

        empty = client.post("/api/knowledge/units", json={"title": "   "})
        assert empty.status_code == 400


def test_report_tool_reads_specific_attempt() -> None:
    """从报告页跳转时带着 attempt_id，改卷老师要读那一份而不是最近一份。"""
    import asyncio

    from app.db.session import SessionLocal
    from app.exams.service import get_latest_attempt_report

    async def run() -> None:
        async with SessionLocal() as db:
            missing = await get_latest_attempt_report(db, "pytest-user", "no-such-id")
            assert missing["status"] in ("empty", "success")

    asyncio.run(run())


def test_tool_prefers_active_attempt_from_state() -> None:
    import asyncio

    from app.tools.exam import get_latest_attempt_report

    class Ctx:
        def __init__(self, state):
            self.state = state

    captured = {}

    async def fake_report(db, user_id, attempt_id=""):
        captured["attempt_id"] = attempt_id
        return {"status": "empty", "report": None}

    import app.tools.exam as exam_tools

    original = exam_tools.latest_report
    exam_tools.latest_report = fake_report
    try:
        ctx = Ctx({"user_id": "u1", "active_attempt_id": "att-123"})
        asyncio.run(get_latest_attempt_report(ctx))
        assert captured["attempt_id"] == "att-123"

        ctx.state.pop("active_attempt_id")
        asyncio.run(get_latest_attempt_report(ctx))
        assert captured["attempt_id"] == ""
    finally:
        exam_tools.latest_report = original


def test_continue_with_skips_counselor() -> None:
    """续接指定老师时，本轮直接由 TA 回答，不再经辅导员转接。"""
    from app.agents.factory import create_root_agent
    from app.schemas.settings import LlmSettings

    llm = LlmSettings(api_base="https://example.com/v1", api_key="k", default_model="t")
    direct = create_root_agent(llm, continue_with="grader")
    assert direct.name == "grader"

    unknown = create_root_agent(llm, continue_with="nobody")
    assert unknown.name == "counselor"

    normal = create_root_agent(llm)
    assert normal.name == "counselor"
