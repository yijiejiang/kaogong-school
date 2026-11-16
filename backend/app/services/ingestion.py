"""Material registration and background ingestion jobs."""

import asyncio
import json
import logging
import shutil
import uuid
from pathlib import Path
from urllib.parse import urlparse

from fastapi import UploadFile
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import DATA_DIR, SAMPLE_DIR, UPLOAD_DIR, get_settings
from app.db.models import Chunk, Job, Material
from app.db.session import SessionLocal
from app.rag.asr import (
    AUDIO_SUFFIXES,
    AsrError,
    AsrUnavailable,
    asr_ready,
    transcribe_file,
    transcribe_video_url,
)
from app.rag.chunking import chunk_text
from app.rag.embeddings import EmbeddingError, get_embedding_service
from app.rag.index import TaggedChunk, replace_chunks
from app.rag.parsers import (
    IMAGE_SUFFIXES,
    FetchError,
    ParsedDocument,
    ParseError,
    UnsafeUrl,
    fetch_url,
    is_public_url,
    parse_file,
    sanitize_filename,
)
from app.rag.tagging import load_prepared_points, tag_text
from app.rag.video import fetch_video, is_video_url
from app.services.settings_service import load_llm_settings

logger = logging.getLogger(__name__)

ALLOWED_SUFFIXES = {
    ".pdf",
    ".docx",
    ".txt",
    ".md",
    ".markdown",
    *IMAGE_SUFFIXES,
    *AUDIO_SUFFIXES,
}
SAMPLE_FILENAME = "资料分析速算.md"

_tasks: set[asyncio.Task] = set()


def resolve_upload_path(relative: str) -> Path:
    path = (DATA_DIR / relative).resolve()
    base = DATA_DIR.resolve()
    if base not in path.parents and path != base:
        raise ParseError("资料路径不合法。")
    return path


async def create_uploaded_material(db: AsyncSession, file: UploadFile) -> Material:
    settings = get_settings()
    filename = sanitize_filename(file.filename or "document")
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ParseError(
            "当前支持 PDF、DOCX、TXT、Markdown、PNG/JPG 图片和常见音频格式。"
        )

    data = await file.read()
    if not data:
        raise ParseError("文件为空。")
    if len(data) > settings.max_upload_bytes:
        raise ParseError("文件超过 50 MB 上限。")

    material_id = uuid.uuid4().hex
    destination = UPLOAD_DIR / material_id / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(destination.write_bytes, data)

    if suffix in IMAGE_SUFFIXES:
        kind = "image"
    elif suffix in AUDIO_SUFFIXES:
        kind = "audio"
    else:
        kind = "file"

    material = Material(
        id=material_id,
        title=Path(filename).stem[:255],
        kind=kind,
        file_path=f"uploads/{material_id}/{filename}",
        filename=filename,
        mime_type=file.content_type or "",
        size_bytes=len(data),
        status="pending",
    )
    db.add(material)
    await db.commit()
    await db.refresh(material)
    await start_ingestion(db, material.id)
    return material


async def create_url_material(db: AsyncSession, url: str) -> Material:
    url = url.strip()
    if not is_public_url(url):
        raise UnsafeUrl("只允许导入公网 http/https 地址。")

    host = urlparse(url).hostname or "网页资料"
    material = Material(
        id=uuid.uuid4().hex,
        title=host[:255],
        kind="video" if is_video_url(url) else "url",
        source_url=url,
        status="pending",
    )
    db.add(material)
    await db.commit()
    await db.refresh(material)
    await start_ingestion(db, material.id)
    return material


async def create_sample_material(db: AsyncSession) -> Material:
    sample_path = SAMPLE_DIR / SAMPLE_FILENAME
    if not sample_path.exists():
        raise ParseError("示例资料不存在，请检查 backend/samples 目录。")

    material_id = uuid.uuid4().hex
    destination = UPLOAD_DIR / material_id / SAMPLE_FILENAME
    destination.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(shutil.copyfile, sample_path, destination)

    material = Material(
        id=material_id,
        title="资料分析速算技巧（示例）",
        kind="sample",
        file_path=f"uploads/{material_id}/{SAMPLE_FILENAME}",
        filename=SAMPLE_FILENAME,
        mime_type="text/markdown",
        size_bytes=destination.stat().st_size,
        status="pending",
    )
    db.add(material)
    await db.commit()
    await db.refresh(material)
    await start_ingestion(db, material.id)
    return material


async def start_ingestion(db: AsyncSession, material_id: str) -> Job:
    job = Job(
        id=uuid.uuid4().hex,
        type="ingest",
        status="pending",
        message="等待入库",
        payload_json=json.dumps({"material_id": material_id}, ensure_ascii=False),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    task = asyncio.create_task(run_ingestion_job(job.id, material_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return job


async def run_ingestion_job(job_id: str, material_id: str) -> None:
    settings = get_settings()
    async with SessionLocal() as db:
        job = await db.get(Job, job_id)
        material = await db.get(Material, material_id)
        if job is None or material is None:
            return

        try:
            job.status = "processing"
            job.progress = 0.05
            job.message = "解析资料"
            material.status = "processing"
            material.error = ""
            await db.commit()

            llm = await load_llm_settings(db)
            if material.kind == "url":
                parsed = await fetch_url(material.source_url, settings.max_url_bytes)
            elif material.kind == "video":
                transcriber = (
                    transcribe_video_url if asr_ready(llm) else None
                )
                parsed = await fetch_video(
                    material.source_url,
                    settings.max_url_bytes,
                    transcriber=transcriber,
                )
            elif material.kind == "audio":
                path = resolve_upload_path(material.file_path)
                if not path.exists():
                    raise ParseError("原始音频不存在，请重新上传。")
                try:
                    result = await transcribe_file(
                        path, llm, filename=material.filename
                    )
                except AsrUnavailable as exc:
                    raise ParseError(str(exc)) from exc
                except AsrError as exc:
                    raise ParseError(f"语音转写失败：{exc}") from exc
                parsed = ParsedDocument(
                    title=material.title or path.stem,
                    text=result.text,
                    pages=[(1, result.text)],
                    kind="audio",
                    mime_type=material.mime_type,
                    warning=f"语音转写：{result.model}",
                )
            else:
                path = resolve_upload_path(material.file_path)
                if not path.exists():
                    raise ParseError("原始文件不存在，请重新上传。")
                parsed = await asyncio.to_thread(
                    parse_file, path, material.filename, material.mime_type
                )

            if parsed.title.strip():
                material.title = parsed.title.strip()[:255]

            job.progress = 0.3
            job.message = "切分内容"
            await db.commit()

            prepared = await load_prepared_points(db)
            tagged: list[TaggedChunk] = []
            if len(parsed.pages) > 1:
                for page_number, page_text in parsed.pages:
                    for item in chunk_text(
                        page_text, settings.chunk_size, settings.chunk_overlap
                    ):
                        tagged.append(
                            TaggedChunk(
                                content=item.content,
                                heading=item.heading,
                                page=page_number,
                                tag=tag_text(item.content, prepared),
                            )
                        )
            else:
                for item in chunk_text(
                    parsed.text, settings.chunk_size, settings.chunk_overlap
                ):
                    tagged.append(
                        TaggedChunk(
                            content=item.content,
                            heading=item.heading,
                            page=item.page,
                            tag=tag_text(item.content, prepared),
                        )
                    )

            if not tagged:
                raise ParseError("没有提取到可索引的文本。")
            if len(tagged) > 1000:
                tagged = tagged[:1000]

            job.progress = 0.45
            job.message = "生成向量"
            await db.commit()

            embedder = get_embedding_service(llm)
            embeddings = await embedder.embed([item.content for item in tagged])

            job.progress = 0.8
            job.message = "写入索引"
            await db.commit()

            count = await replace_chunks(
                db, material, tagged, embeddings, embedder.name
            )
            material.status = "ready"
            material.error = ""
            job.status = "done"
            job.progress = 1.0
            job.message = (
                f"已索引 {count} 个分块。{parsed.warning}"
                if parsed.warning
                else f"已索引 {count} 个分块。"
            )
            job.result_json = json.dumps(
                {
                    "chunk_count": count,
                    "embedding_model": embedder.name,
                    "warning": parsed.warning,
                },
                ensure_ascii=False,
            )
            await db.commit()
        except (ParseError, FetchError, UnsafeUrl, EmbeddingError) as exc:
            await _mark_failed(db, job_id, material_id, str(exc))
        except Exception as exc:
            logger.exception("ingestion job failed")
            await _mark_failed(db, job_id, material_id, str(exc))


async def _mark_failed(
    db: AsyncSession, job_id: str, material_id: str, error: str
) -> None:
    await db.rollback()
    job = await db.get(Job, job_id)
    material = await db.get(Material, material_id)
    if job is not None:
        job.status = "failed"
        job.message = "入库失败"
        job.error = error[:1000]
    if material is not None:
        material.status = "failed"
        material.error = error[:1000]
    await db.commit()


async def recover_stale_jobs() -> None:
    async with SessionLocal() as db:
        await db.execute(
            update(Job)
            .where(Job.status.in_(["pending", "processing"]))
            .values(
                status="failed",
                message="已中断",
                error="服务重启，请重新索引。",
            )
        )
        await db.execute(
            update(Material)
            .where(Material.status.in_(["pending", "processing"]))
            .values(status="failed", error="服务重启，请重新索引。")
        )
        await db.commit()


async def reindex_material(db: AsyncSession, material_id: str) -> Material:
    material = await db.get(Material, material_id)
    if material is None:
        raise ParseError("资料不存在。")
    if material.status == "processing":
        raise ParseError("资料正在入库，请稍后再试。")

    await db.execute(delete(Chunk).where(Chunk.material_id == material_id))
    material.status = "pending"
    material.error = ""
    material.chunk_count = 0
    await db.commit()
    await start_ingestion(db, material_id)
    return material


async def delete_material(db: AsyncSession, material_id: str) -> bool:
    material = await db.get(Material, material_id)
    if material is None:
        return False

    await db.execute(delete(Chunk).where(Chunk.material_id == material_id))
    await db.delete(material)
    await db.commit()

    folder = UPLOAD_DIR / material_id
    if folder.exists():
        await asyncio.to_thread(shutil.rmtree, folder, True)
    return True


async def latest_job_for_material(db: AsyncSession, material_id: str) -> Job | None:
    result = await db.execute(
        select(Job)
        .where(Job.type == "ingest", Job.payload_json.contains(material_id))
        .order_by(Job.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
