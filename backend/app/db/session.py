from collections.abc import AsyncIterator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import DATA_DIR, get_settings
from app.db.models import Base

settings = get_settings()
DATA_DIR.mkdir(parents=True, exist_ok=True)

_is_sqlite = settings.database_url.startswith("sqlite")
# 写锁等待上限：超时就抛错，而不是让请求一直挂到前端超时。
_SQLITE_LOCK_TIMEOUT = 10
_connect_args = {"timeout": _SQLITE_LOCK_TIMEOUT} if _is_sqlite else {}
engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    connect_args=_connect_args,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@event.listens_for(engine.sync_engine, "connect")
def _configure_sqlite(dbapi_connection, _record) -> None:
    """把 SQLite 调成适合多请求并发读写的模式。

    WAL：写事务进行时读请求照常进行，一个慢的批量写入不会让整个界面失去响应。
    busy_timeout：拿不到写锁时最多等这么久就报错，避免请求无限挂起。
    """
    if not _is_sqlite:
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(f"PRAGMA busy_timeout={_SQLITE_LOCK_TIMEOUT * 1000}")
        cursor.execute("PRAGMA synchronous=NORMAL")
    finally:
        cursor.close()


CHUNK_COLUMNS = {
    "heading_path": "VARCHAR(512) NOT NULL DEFAULT ''",
    "chunk_type": "VARCHAR(16) NOT NULL DEFAULT 'summary'",
    "labels_json": "TEXT NOT NULL DEFAULT '[]'",
    "time_start": "FLOAT",
    "time_end": "FLOAT",
    "frame_path": "VARCHAR(512) NOT NULL DEFAULT ''",
    "page_image_path": "VARCHAR(512) NOT NULL DEFAULT ''",
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
    "evidence_note": "TEXT NOT NULL DEFAULT ''",
}

SKILL_COLUMNS = {
    "exam_patterns_json": "TEXT NOT NULL DEFAULT '[]'",
    "signals_json": "TEXT NOT NULL DEFAULT '[]'",
    "variants_json": "TEXT NOT NULL DEFAULT '[]'",
    "connections_json": "TEXT NOT NULL DEFAULT '[]'",
    "question_design_json": "TEXT NOT NULL DEFAULT '[]'",
    "difficulty": "INTEGER NOT NULL DEFAULT 3",
    "source": "VARCHAR(32) NOT NULL DEFAULT 'manual'",
    "source_ref": "VARCHAR(255) NOT NULL DEFAULT ''",
}

QUESTION_COLUMNS = {
    "skill_id": "VARCHAR(64) NOT NULL DEFAULT ''",
    "skill_name": "VARCHAR(128) NOT NULL DEFAULT ''",
    "tags_json": "TEXT NOT NULL DEFAULT '[]'",
    "material_id": "VARCHAR(36) NOT NULL DEFAULT ''",
}

USAGE_COLUMNS = {
    "provider": "VARCHAR(64) NOT NULL DEFAULT ''",
    "service": "VARCHAR(32) NOT NULL DEFAULT 'llm'",
    "units": "FLOAT NOT NULL DEFAULT 0",
    "billing_mode": "VARCHAR(16) NOT NULL DEFAULT 'payg'",
    "note": "TEXT NOT NULL DEFAULT ''",
}

NOTIFICATION_COLUMNS = {
    "link": "VARCHAR(512) NOT NULL DEFAULT ''",
}

_TABLE_COLUMNS = {
    "chunks": CHUNK_COLUMNS,
    "knowledge_units": KNOWLEDGE_UNIT_COLUMNS,
    "skills": SKILL_COLUMNS,
    "questions": QUESTION_COLUMNS,
    "llm_usage": USAGE_COLUMNS,
    "notifications": NOTIFICATION_COLUMNS,
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


async def _relax_knowledge_unit_source(conn) -> None:
    """知识条目允许没有来源资料（手动新增）。

    SQLite 不能直接去掉列的 NOT NULL，只能重建表再把数据搬回去。
    """
    result = await conn.execute(text("PRAGMA table_info(knowledge_units)"))
    info = {row[1]: row for row in result}
    if not info:
        return
    material_notnull = info.get("material_id", (None,) * 4)[3]
    chunk_notnull = info.get("chunk_id", (None,) * 4)[3]
    if not material_notnull and not chunk_notnull:
        return

    await conn.execute(
        text(
            "CREATE TABLE knowledge_units_new ("
            " id VARCHAR(36) NOT NULL PRIMARY KEY,"
            " material_id VARCHAR(36),"
            " chunk_id VARCHAR(36),"
            " chunk_type VARCHAR(16), title VARCHAR(255), summary TEXT,"
            " definition TEXT, conditions_json TEXT, steps_json TEXT,"
            " pitfalls_json TEXT, examples_json TEXT, exam_pattern TEXT,"
            " signals_json TEXT, variants_json TEXT, connections_json TEXT,"
            " question_design_json TEXT, knowledge_point_id VARCHAR(64),"
            " knowledge_point_name VARCHAR(128), skill_name VARCHAR(128),"
            " skill_id VARCHAR(64), proposed_knowledge_point VARCHAR(128),"
            " proposed_parent_id VARCHAR(64), proposed_reason TEXT,"
            " confidence FLOAT, evidence_json TEXT, extraction_model VARCHAR(128),"
            " status VARCHAR(16), created_at DATETIME, updated_at DATETIME,"
            " FOREIGN KEY(material_id) REFERENCES materials(id) ON DELETE CASCADE,"
            " FOREIGN KEY(chunk_id) REFERENCES chunks(id) ON DELETE CASCADE)"
        )
    )
    columns = ", ".join(info.keys())
    await conn.execute(
        text(
            f"INSERT INTO knowledge_units_new ({columns}) "
            f"SELECT {columns} FROM knowledge_units"
        )
    )
    await conn.execute(text("DROP TABLE knowledge_units"))
    await conn.execute(
        text("ALTER TABLE knowledge_units_new RENAME TO knowledge_units")
    )
    await conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_knowledge_units_material_id "
            "ON knowledge_units (material_id)"
        )
    )
    await conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_knowledge_units_chunk_id "
            "ON knowledge_units (chunk_id)"
        )
    )


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_columns(conn)
        if engine.dialect.name == "sqlite":
            await _relax_knowledge_unit_source(conn)
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_questions_material_id "
                "ON questions (material_id)"
            )
        )


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
