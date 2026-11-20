from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import DATA_DIR, get_settings
from app.db.models import Base

settings = get_settings()
DATA_DIR.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(settings.database_url, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

CHUNK_COLUMNS = {
    "heading_path": "VARCHAR(512) NOT NULL DEFAULT ''",
    "chunk_type": "VARCHAR(16) NOT NULL DEFAULT 'summary'",
    "labels_json": "TEXT NOT NULL DEFAULT '[]'",
    "time_start": "FLOAT",
    "time_end": "FLOAT",
    "frame_path": "VARCHAR(512) NOT NULL DEFAULT ''",
}

KNOWLEDGE_UNIT_COLUMNS = {
    "skill_name": "VARCHAR(128) NOT NULL DEFAULT ''",
    "exam_pattern": "TEXT NOT NULL DEFAULT ''",
    "signals_json": "TEXT NOT NULL DEFAULT '[]'",
    "variants_json": "TEXT NOT NULL DEFAULT '[]'",
    "connections_json": "TEXT NOT NULL DEFAULT '[]'",
    "question_design_json": "TEXT NOT NULL DEFAULT '[]'",
    "proposed_knowledge_point": "VARCHAR(128) NOT NULL DEFAULT ''",
    "proposed_parent_id": "VARCHAR(64) NOT NULL DEFAULT ''",
    "proposed_reason": "TEXT NOT NULL DEFAULT ''",
}

SKILL_COLUMNS = {
    "exam_patterns_json": "TEXT NOT NULL DEFAULT '[]'",
    "signals_json": "TEXT NOT NULL DEFAULT '[]'",
    "variants_json": "TEXT NOT NULL DEFAULT '[]'",
    "connections_json": "TEXT NOT NULL DEFAULT '[]'",
    "question_design_json": "TEXT NOT NULL DEFAULT '[]'",
    "difficulty": "INTEGER NOT NULL DEFAULT 3",
}

QUESTION_COLUMNS = {
    "skill_id": "VARCHAR(64) NOT NULL DEFAULT ''",
    "skill_name": "VARCHAR(128) NOT NULL DEFAULT ''",
}

_TABLE_COLUMNS = {
    "chunks": CHUNK_COLUMNS,
    "knowledge_units": KNOWLEDGE_UNIT_COLUMNS,
    "skills": SKILL_COLUMNS,
    "questions": QUESTION_COLUMNS,
}


async def _ensure_columns(conn) -> None:
    dialect = conn.dialect.name
    for table, columns in _TABLE_COLUMNS.items():
        if dialect == "sqlite":
            result = await conn.execute(text(f"PRAGMA table_info({table})"))
            existing = {row[1] for row in result}
            for name, ddl in columns.items():
                if name not in existing:
                    await conn.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
                    )
        elif dialect == "postgresql":
            for name, ddl in columns.items():
                await conn.execute(
                    text(
                        f"ALTER TABLE {table} "
                        f"ADD COLUMN IF NOT EXISTS {name} {ddl}"
                    )
                )


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_columns(conn)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
