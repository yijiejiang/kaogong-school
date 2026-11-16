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


class ChunkOut(BaseModel):
    id: str
    chunk_index: int
    content: str
    page: int | None = None
    heading: str = ""
    subject: str = ""
    module: str = ""
    knowledge_point_id: str = ""
    knowledge_point_name: str = ""
    tags: list[str] = Field(default_factory=list)


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
    heading: str = ""
    content: str
    score: float
    subject: str = ""
    module: str = ""
    knowledge_point_id: str = ""
    knowledge_point_name: str = ""
    tags: list[str] = Field(default_factory=list)


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
