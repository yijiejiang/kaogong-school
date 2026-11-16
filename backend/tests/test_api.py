import json
import os
import tempfile
import time
from pathlib import Path

import pytest

TEST_DB = Path(tempfile.gettempdir()) / "kaogong_pytest.db"
os.environ["MOCK_LLM"] = "1"
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

        search = client.post(
            "/api/search", json={"query": "资料分析速算技巧", "top_k": 5}
        )
        assert search.status_code == 200
        body = search.json()
        assert body["results"]
        assert any("截位" in item["content"] for item in body["results"])
        assert any(card["kp_id"] == "xingce-ziliao-susuan" for card in body["cards"])


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
        assert '"to": "knowledge"' in body
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
        connection = sqlite3.connect(TEST_DB)
        connection.execute(
            "INSERT INTO llm_usage (id, user_id, session_id, role, model, "
            "prompt_tokens, completion_tokens, total_tokens, cost, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                uuid.uuid4().hex,
                user_id,
                "s_test",
                "counselor",
                "test-model",
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



