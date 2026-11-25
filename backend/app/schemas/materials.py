from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MaterialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    kind: str
    status: str
    subject: str = ""
    module: str = ""
    chunk_count: int = 0
    error: str = ""
    filename: str = ""
    source_url: str = ""
    size_bytes: int = 0
    embedding_model: str = ""
    created_at: datetime
    updated_at: datetime


class ChunkLabelOut(BaseModel):
    knowledge_point_id: str = ""
    knowledge_point_name: str = ""
    subject: str = ""
    module: str = ""
    score: float = 0.0
    confidence: float = 0.0
    tags: list[str] = Field(default_factory=list)


class ChunkOut(BaseModel):
    id: str
    chunk_index: int
    content: str
    page: int | None = None
    time_start: float | None = None
    time_end: float | None = None
    frame_url: str = ""
    heading: str = ""
    heading_path: str = ""
    chunk_type: str = "summary"
    subject: str = ""
    module: str = ""
    knowledge_point_id: str = ""
    knowledge_point_name: str = ""
    tags: list[str] = Field(default_factory=list)
    labels: list[ChunkLabelOut] = Field(default_factory=list)


class MaterialDetail(BaseModel):
    material: MaterialOut
    chunks: list[ChunkOut]


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    status: str
    progress: float
    message: str = ""
    error: str = ""
    created_at: datetime
    updated_at: datetime


class UrlImportRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    subject: str = ""
    module: str = ""
    top_k: int = Field(default=8, ge=1, le=30)


class SearchHit(BaseModel):
    chunk_id: str
    material_id: str
    material_title: str
    page: int | None = None
    time_start: float | None = None
    time_end: float | None = None
    frame_url: str = ""
    heading: str = ""
    heading_path: str = ""
    chunk_type: str = "summary"
    content: str
    score: float
    subject: str = ""
    module: str = ""
    knowledge_point_id: str = ""
    knowledge_point_name: str = ""
    tags: list[str] = Field(default_factory=list)
    labels: list[ChunkLabelOut] = Field(default_factory=list)


class KnowledgeCardHit(BaseModel):
    kp_id: str
    title: str
    summary: str
    methods: str = ""
    traps: str = ""


class SearchResponse(BaseModel):
    query: str
    results: list[SearchHit]
    cards: list[KnowledgeCardHit]


class KnowledgeNode(BaseModel):
    id: str
    parent_id: str | None = None
    name: str
    subject: str = ""
    module: str = ""
    level: int = 1
    description: str = ""
    keywords: list[str] = Field(default_factory=list)
    chunk_count: int = 0


class KnowledgeCardOut(BaseModel):
    kp_id: str
    title: str
    summary: str
    methods: str = ""
    traps: str = ""
    source_chunks: list[SearchHit] = Field(default_factory=list)


class KnowledgeUnitOut(BaseModel):
    id: str
    material_id: str | None = None
    chunk_id: str | None = None
    chunk_type: str
    title: str
    summary: str = ""
    definition: str = ""
    conditions: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    pitfalls: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    exam_pattern: str = ""
    signals: list[str] = Field(default_factory=list)
    variants: list[str] = Field(default_factory=list)
    connections: list[dict] = Field(default_factory=list)
    question_design: list[str] = Field(default_factory=list)
    knowledge_point_id: str = ""
    knowledge_point_name: str = ""
    skill_name: str = ""
    skill_id: str = ""
    proposed_knowledge_point: str = ""
    proposed_parent_id: str = ""
    proposed_reason: str = ""
    confidence: float = 0.0
    status: str = "draft"
    evidence: list[dict] = Field(default_factory=list)
    extraction_model: str = ""
    created_at: datetime
    updated_at: datetime


class KnowledgeUnitCreate(BaseModel):
    title: str = ""
    summary: str = ""
    definition: str = ""
    conditions: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    pitfalls: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    exam_pattern: str = ""
    signals: list[str] = Field(default_factory=list)
    variants: list[str] = Field(default_factory=list)
    knowledge_point_id: str = ""
    knowledge_point_name: str = ""


class KnowledgeUnitUpdate(BaseModel):
    title: str | None = None
    summary: str | None = None
    definition: str | None = None
    conditions: list[str] | None = None
    steps: list[str] | None = None
    pitfalls: list[str] | None = None
    examples: list[str] | None = None
    exam_pattern: str | None = None
    signals: list[str] | None = None
    variants: list[str] | None = None
    connections: list[dict] | None = None
    question_design: list[str] | None = None
    knowledge_point_id: str | None = None
    knowledge_point_name: str | None = None
    status: str | None = None


class SkillOut(BaseModel):
    id: str
    name: str
    normalized_name: str
    subject: str = ""
    module: str = ""
    knowledge_point_id: str = ""
    knowledge_point_name: str = ""
    summary: str = ""
    conditions: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    pitfalls: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    exam_patterns: list[str] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)
    variants: list[str] = Field(default_factory=list)
    connections: list[dict] = Field(default_factory=list)
    question_design: list[str] = Field(default_factory=list)
    difficulty: int = 3
    source_unit_ids: list[str] = Field(default_factory=list)
    source: str = "manual"
    source_ref: str = ""
    confidence: float = 0.0
    status: str = "draft"
    created_at: datetime
    updated_at: datetime


class SkillUpdate(BaseModel):
    name: str | None = None
    summary: str | None = None
    status: str | None = None
