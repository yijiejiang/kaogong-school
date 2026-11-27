from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    kind: Mapped[str] = mapped_column(String(16), default="file")
    source_url: Mapped[str] = mapped_column(Text, default="")
    file_path: Mapped[str] = mapped_column(Text, default="")
    filename: Mapped[str] = mapped_column(String(255), default="")
    mime_type: Mapped[str] = mapped_column(String(128), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    error: Mapped[str] = mapped_column(Text, default="")
    subject: Mapped[str] = mapped_column(String(32), default="")
    module: Mapped[str] = mapped_column(String(64), default="")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding_model: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    material_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("materials.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    embedding_json: Mapped[str] = mapped_column(Text, default="[]")
    embedding_dim: Mapped[int] = mapped_column(Integer, default=0)
    embedding_model: Mapped[str] = mapped_column(String(128), default="")
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_start: Mapped[float | None] = mapped_column(Float, nullable=True)
    time_end: Mapped[float | None] = mapped_column(Float, nullable=True)
    frame_path: Mapped[str] = mapped_column(String(512), default="")
    # 扫描页/图表页的原页图片，供需要视觉识别的场景回看
    page_image_path: Mapped[str] = mapped_column(String(512), default="")
    heading: Mapped[str] = mapped_column(String(255), default="")
    heading_path: Mapped[str] = mapped_column(String(512), default="")
    chunk_type: Mapped[str] = mapped_column(String(16), default="summary", index=True)
    subject: Mapped[str] = mapped_column(String(32), default="")
    module: Mapped[str] = mapped_column(String(64), default="")
    knowledge_point_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    knowledge_point_name: Mapped[str] = mapped_column(String(128), default="")
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    labels_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class KnowledgePoint(Base):
    __tablename__ = "knowledge_points"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    parent_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(128))
    subject: Mapped[str] = mapped_column(String(32), default="")
    module: Mapped[str] = mapped_column(String(64), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    keywords_json: Mapped[str] = mapped_column(Text, default="[]")
    level: Mapped[int] = mapped_column(Integer, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class KnowledgeCard(Base):
    __tablename__ = "knowledge_cards"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(128), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    methods: Mapped[str] = mapped_column(Text, default="")
    traps: Mapped[str] = mapped_column(Text, default="")
    source_chunk_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class KnowledgeUnit(Base):
    __tablename__ = "knowledge_units"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # 手动新增的知识条目没有来源资料，这两个字段可以为空
    material_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("materials.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    chunk_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("chunks.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    chunk_type: Mapped[str] = mapped_column(String(16), default="summary")
    title: Mapped[str] = mapped_column(String(255), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    definition: Mapped[str] = mapped_column(Text, default="")
    conditions_json: Mapped[str] = mapped_column(Text, default="[]")
    steps_json: Mapped[str] = mapped_column(Text, default="[]")
    pitfalls_json: Mapped[str] = mapped_column(Text, default="[]")
    examples_json: Mapped[str] = mapped_column(Text, default="[]")
    exam_pattern: Mapped[str] = mapped_column(Text, default="")
    signals_json: Mapped[str] = mapped_column(Text, default="[]")
    variants_json: Mapped[str] = mapped_column(Text, default="[]")
    connections_json: Mapped[str] = mapped_column(Text, default="[]")
    question_design_json: Mapped[str] = mapped_column(Text, default="[]")
    knowledge_point_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    knowledge_point_name: Mapped[str] = mapped_column(String(128), default="")
    skill_name: Mapped[str] = mapped_column(String(128), default="")
    skill_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    proposed_knowledge_point: Mapped[str] = mapped_column(String(128), default="")
    proposed_parent_id: Mapped[str] = mapped_column(String(64), default="")
    proposed_reason: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    evidence_json: Mapped[str] = mapped_column(Text, default="[]")
    extraction_model: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    normalized_name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    subject: Mapped[str] = mapped_column(String(32), default="")
    module: Mapped[str] = mapped_column(String(64), default="")
    knowledge_point_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    knowledge_point_name: Mapped[str] = mapped_column(String(128), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    conditions_json: Mapped[str] = mapped_column(Text, default="[]")
    steps_json: Mapped[str] = mapped_column(Text, default="[]")
    pitfalls_json: Mapped[str] = mapped_column(Text, default="[]")
    examples_json: Mapped[str] = mapped_column(Text, default="[]")
    exam_patterns_json: Mapped[str] = mapped_column(Text, default="[]")
    signals_json: Mapped[str] = mapped_column(Text, default="[]")
    variants_json: Mapped[str] = mapped_column(Text, default="[]")
    connections_json: Mapped[str] = mapped_column(Text, default="[]")
    question_design_json: Mapped[str] = mapped_column(Text, default="[]")
    difficulty: Mapped[int] = mapped_column(Integer, default=3)
    source_unit_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    # 技能来源：huasheng13 / manual / extraction
    source: Mapped[str] = mapped_column(String(32), default="manual", index=True)
    source_ref: Mapped[str] = mapped_column(String(255), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    message: Mapped[str] = mapped_column(String(255), default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(16), default="single")
    subject: Mapped[str] = mapped_column(String(32), default="行测")
    module: Mapped[str] = mapped_column(String(64), default="资料分析")
    knowledge_point_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    knowledge_point_name: Mapped[str] = mapped_column(String(128), default="")
    skill_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    skill_name: Mapped[str] = mapped_column(String(128), default="")
    stem: Mapped[str] = mapped_column(Text)
    options_json: Mapped[str] = mapped_column(Text, default="[]")
    answer_json: Mapped[str] = mapped_column(Text, default="{}")
    rubric_json: Mapped[str] = mapped_column(Text, default="[]")
    explanation: Mapped[str] = mapped_column(Text, default="")
    difficulty: Mapped[int] = mapped_column(Integer, default=3)
    source: Mapped[str] = mapped_column(String(32), default="seed")
    # 细化标签，例如 牛吃草 / 概率 / 新闻类 / 说理类
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    material_id: Mapped[str] = mapped_column(String(36), default="", index=True)
    quality_status: Mapped[str] = mapped_column(String(16), default="approved")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    subject: Mapped[str] = mapped_column(String(32), default="行测")
    module: Mapped[str] = mapped_column(String(64), default="资料分析")
    question_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=35)
    difficulty: Mapped[str] = mapped_column(String(16), default="medium")
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    blueprint_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(16), default="ready")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class ExamQuestion(Base):
    __tablename__ = "exam_questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    exam_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("exams.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("questions.id"), index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float] = mapped_column(Float, default=3.0)


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("exams.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(64), default="local-user", index=True)
    status: Mapped[str] = mapped_column(String(16), default="in_progress", index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    score: Mapped[float] = mapped_column(Float, default=0.0)
    total_score: Mapped[float] = mapped_column(Float, default=0.0)
    report_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class ExtractScope(Base):
    """一份资料的一次抽取，按范围拆开逐个处理。

    长资料不能整份塞给模型，也不能只取前若干块。这里按章节或页段切成
    互不重叠的范围，每段独立记录状态和尝试次数，失败只重跑这一段。
    """

    __tablename__ = "extract_scopes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    material_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("materials.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(16), default="question", index=True)
    # 文档版本：资料重新入库后旧范围的键不再命中，避免重复写入
    doc_version: Mapped[str] = mapped_column(String(64), default="", index=True)
    scope_key: Mapped[str] = mapped_column(String(128), default="")
    title: Mapped[str] = mapped_column(String(255), default="")
    page_start: Mapped[int] = mapped_column(Integer, default=0)
    page_end: Mapped[int] = mapped_column(Integer, default=0)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    found: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    attempt_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("attempts.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("questions.id"), index=True
    )
    response_json: Mapped[str] = mapped_column(Text, default="{}")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    max_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    feedback_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Mastery(Base):
    __tablename__ = "mastery"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    knowledge_point_id: Mapped[str] = mapped_column(String(64), index=True)
    knowledge_point_name: Mapped[str] = mapped_column(String(128), default="")
    score: Mapped[float] = mapped_column(Float, default=50.0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    last_practiced: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class SkillMastery(Base):
    __tablename__ = "skill_mastery"

    id: Mapped[str] = mapped_column(String(192), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    skill_id: Mapped[str] = mapped_column(String(64), index=True)
    skill_name: Mapped[str] = mapped_column(String(128), default="")
    score: Mapped[float] = mapped_column(Float, default=50.0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    last_practiced: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class ErrorBook(Base):
    __tablename__ = "error_book"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    question_id: Mapped[str] = mapped_column(String(64), index=True)
    attempt_id: Mapped[str] = mapped_column(String(36), default="")
    knowledge_point_id: Mapped[str] = mapped_column(String(64), default="")
    knowledge_point_name: Mapped[str] = mapped_column(String(128), default="")
    error_type: Mapped[str] = mapped_column(String(32), default="wrong")
    times_wrong: Mapped[int] = mapped_column(Integer, default=1)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    week_start: Mapped[str] = mapped_column(String(10), index=True)
    goal: Mapped[str] = mapped_column(Text, default="")
    meta_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class PlanTask(Base):
    __tablename__ = "plan_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plans.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    date: Mapped[str] = mapped_column(String(10), index=True)
    task_type: Mapped[str] = mapped_column(String(16), default="practice")
    title: Mapped[str] = mapped_column(String(255), default="")
    knowledge_point_id: Mapped[str] = mapped_column(String(64), default="")
    knowledge_point_name: Mapped[str] = mapped_column(String(128), default="")
    minutes: Mapped[int] = mapped_column(Integer, default=20)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    dedupe_key: Mapped[str] = mapped_column(
        String(160), unique=True, index=True
    )
    read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class LlmUsage(Base):
    __tablename__ = "llm_usage"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    session_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    role: Mapped[str] = mapped_column(String(32), default="", index=True)
    model: Mapped[str] = mapped_column(String(128), default="")
    provider: Mapped[str] = mapped_column(
        String(64), default="", server_default="", index=True
    )
    service: Mapped[str] = mapped_column(
        String(32), default="llm", server_default="llm", index=True
    )
    units: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    billing_mode: Mapped[str] = mapped_column(
        String(16), default="payg", server_default="payg"
    )
    note: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
