import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    analytics,
    asr,
    chat,
    exams,
    health,
    knowledge,
    materials,
    notifications,
    plan,
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
    scheduler = asyncio.create_task(notification_loop())
    yield
    scheduler.cancel()
    with suppress(asyncio.CancelledError):
        await scheduler


app = FastAPI(title="考公私塾 API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(settings.router)
app.include_router(chat.router)
app.include_router(materials.router)
app.include_router(knowledge.router)
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
