import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.api import (
    analytics,
    asr,
    chat,
    connect,
    exams,
    health,
    knowledge,
    materials,
    notifications,
    plan,
    questions,
    settings,
    users,
)
from app.config import DATA_DIR, UPLOAD_DIR, get_settings
from app.db.session import SessionLocal, init_db
from app.exams.bank import seed_question_bank
from app.knowledge.seed import seed_knowledge_tree
from app.services.ingestion import recover_stale_jobs
from app.services.scheduler import notification_loop

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

cfg = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    await init_db()
    async with SessionLocal() as db:
        await seed_knowledge_tree(db)
        await seed_question_bank(db)
    await recover_stale_jobs()
    scheduler = (
        asyncio.create_task(notification_loop()) if cfg.enable_scheduler else None
    )
    yield
    if scheduler is not None:
        scheduler.cancel()
        with suppress(asyncio.CancelledError):
            await scheduler


app = FastAPI(title="考公私塾 API", version="0.1.0", lifespan=lifespan)


@app.exception_handler(OperationalError)
async def handle_db_busy(_request: Request, exc: OperationalError) -> JSONResponse:
    """数据库被长时间占用时给出可读的提示。

    默认情况下这里会拖到前端超时，界面上只显示「Failed to fetch」，
    分不清是网络断了还是后端忙。
    """
    message = str(exc.orig or exc)
    if "locked" in message or "busy" in message:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "数据库正忙（有大批量写入正在进行），请稍后重试。"
            },
        )
    logger.exception("database error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "数据库操作失败。"})


app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(connect.router)
app.include_router(settings.router)
app.include_router(chat.router)
app.include_router(materials.router)
app.include_router(knowledge.router)
app.include_router(questions.router)
app.include_router(asr.router)
app.include_router(exams.router)
app.include_router(analytics.router)
app.include_router(plan.router)
app.include_router(notifications.router)
app.include_router(users.router)


@app.get("/")
async def index() -> dict:
    return {
        "name": "考公私塾 API",
        "docs": "/docs",
        "health": "/api/health",
        "mock_mode": cfg.mock_llm,
    }
