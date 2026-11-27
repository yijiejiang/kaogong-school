"""Material registration and background ingestion jobs."""

import asyncio
import json
import logging
import shutil
import uuid
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from urllib.parse import urlparse

from fastapi import UploadFile
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import DATA_DIR, SAMPLE_DIR, UPLOAD_DIR, get_settings
from app.db.models import Chunk, Job, KnowledgeUnit, Material
from app.db.session import SessionLocal
from app.rag.asr import (
    AUDIO_SUFFIXES,
    AsrError,
    AsrUnavailable,
    asr_ready,
    drain_asr_seconds,
    transcribe_file,
    transcribe_video_url,
)
from app.rag.chunking import chunk_text
from app.rag.embeddings import EmbeddingError, get_embedding_service
from app.rag.extraction import extract_material_units
from app.rag.index import TaggedChunk, replace_chunks
from app.rag.parsers import (
    IMAGE_SUFFIXES,
    FetchError,
    ParsedDocument,
    ParseError,
    UnsafeUrl,
    drain_ocr_pages,
    fetch_url,
    is_public_url,
    parse_file,
    sanitize_filename,
)
from app.rag.tagging import load_prepared_points, tag_text_multi
from app.rag.video import fetch_video, is_video_url
from app.rag.video_slides import (
    VideoSlidesError,
    analyze_video,
    clear_frames,
    drain_summary_usage,
    slide_chunks,
)
from app.services.deepseek_tools import resolve_config as resolve_deepseek
from app.services.llm import role_model_config
from app.services.question_extraction import extract_questions
from app.services.settings_service import load_llm_settings
from app.services.usage import record_service_usage, record_usage

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


@dataclass
class RawChunk:
    content: str
    heading: str = ""
    heading_path: str = ""
    page: int | None = None
    time_start: float | None = None
    time_end: float | None = None
    frame_path: str = ""
    page_image_path: str = ""


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

    material_id = uuid.uuid4().hex
    destination = UPLOAD_DIR / material_id / filename
    destination.parent.mkdir(parents=True, exist_ok=True)

    # 分块流式落盘，避免大文件整体读进内存
    size = 0
    limit = settings.max_upload_bytes
    chunk_size = 1024 * 1024
    try:
        with destination.open("wb") as handle:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    raise ParseError(
                        f"文件超过 {limit // (1024 * 1024)} MB 上限。"
                        "可以在 backend/.env 里改 MAX_UPLOAD_BYTES。"
                    )
                await asyncio.to_thread(handle.write, chunk)
    except ParseError:
        await asyncio.to_thread(shutil.rmtree, destination.parent, True)
        raise
    except Exception as exc:  # 落盘失败要和解析错误区分
        await asyncio.to_thread(shutil.rmtree, destination.parent, True)
        raise ParseError(f"文件写入失败：{exc}") from exc

    if size == 0:
        await asyncio.to_thread(shutil.rmtree, destination.parent, True)
        raise ParseError("文件为空。")

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
        size_bytes=size,
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
            deepseek = resolve_deepseek(llm)
            slide_items: list[dict] | None = None
            if material.kind == "url":
                parsed = await fetch_url(
                    material.source_url, settings.max_url_bytes, deepseek
                )
            elif material.kind == "video":
                transcriber = (
                    partial(transcribe_video_url, llm=llm)
                    if asr_ready(llm)
                    else None
                )
                clear_frames(material.id)
                try:
                    analysis = await analyze_video(
                        material.source_url,
                        material.id,
                        llm,
                        settings.max_url_bytes,
                        transcriber=transcriber,
                    )
                    slide_items = slide_chunks(analysis)
                    text = "\n\n".join(
                        item["content"] for item in slide_items
                    )
                    parsed = ParsedDocument(
                        title=analysis.title,
                        text=text,
                        pages=[(1, text)],
                        kind="video",
                        mime_type="text/vtt",
                        warning=analysis.warning,
                    )
                except VideoSlidesError as exc:
                    parsed = await fetch_video(
                        material.source_url,
                        settings.max_url_bytes,
                        transcriber=transcriber,
                    )
                    parsed.warning = "；".join(
                        item
                        for item in (
                            f"逐页解析失败，已回退字幕/语音稿：{exc}",
                            parsed.warning,
                        )
                        if item
                    )
            elif material.kind == "audio":
                path = resolve_upload_path(material.file_path)
                if not path.exists():
                    raise ParseError("原始音频不存在，请重新上传。")
                try:
                    result = await transcribe_file(
                        path, llm, filename=material.filename, deepseek=deepseek
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
                    parse_file,
                    path,
                    material.filename,
                    material.mime_type,
                    deepseek,
                )

            if parsed.title.strip():
                material.title = parsed.title.strip()[:255]

            # 稀疏页（扫描页/纯图表页）渲染成图片，留着原页引用。
            # 这样后续需要视觉识别时能直接拿到那一页，不用重解析。
            page_images: dict[int, str] = {}
            rendered_count = 0
            if material.kind == "file" and parsed.pages:
                from app.rag.page_images import find_sparse_pages, render_pages

                sparse = find_sparse_pages(parsed.pages)
                if sparse:
                    src = resolve_upload_path(material.file_path)
                    if src.suffix.lower() == ".pdf" and src.exists():
                        out_dir = UPLOAD_DIR / material.id / "pages"
                        try:
                            rendered = await asyncio.to_thread(
                                render_pages, src, sparse, out_dir
                            )
                            for image in rendered:
                                rel = image.path.relative_to(UPLOAD_DIR)
                                page_images[image.page] = str(rel)
                            rendered_count = len(rendered)
                        except Exception:
                            logger.warning(
                                "render sparse pages failed", exc_info=True
                            )

            job.progress = 0.3
            job.message = "切分内容"
            await db.commit()

            raw_chunks: list[RawChunk] = []
            if slide_items is not None:
                raw_chunks = [
                    RawChunk(
                        content=item["content"],
                        heading=item["heading"],
                        heading_path=item["heading_path"],
                        page=item.get("page"),
                        time_start=item.get("time_start"),
                        time_end=item.get("time_end"),
                        frame_path=item.get("frame_path", ""),
                    )
                    for item in slide_items
                ]
            elif len(parsed.pages) > 1:
                for page_number, page_text in parsed.pages:
                    for item in chunk_text(
                        page_text, settings.chunk_size, settings.chunk_overlap
                    ):
                        raw_chunks.append(
                            RawChunk(
                                content=item.content,
                                heading=item.heading,
                                heading_path=item.heading_path,
                                page=page_number,
                                page_image_path=page_images.get(page_number, ""),
                            )
                        )
            else:
                for item in chunk_text(
                    parsed.text, settings.chunk_size, settings.chunk_overlap
                ):
                    raw_chunks.append(
                        RawChunk(
                            content=item.content,
                            heading=item.heading,
                            heading_path=item.heading_path,
                            page=item.page,
                        )
                    )

            if not raw_chunks:
                raise ParseError("没有提取到可索引的文本。")
            raw_chunks = raw_chunks[:1000]

            job.progress = 0.4
            job.message = "生成向量"
            await db.commit()

            embedder = get_embedding_service(llm)
            embeddings = await embedder.embed(
                [item.content for item in raw_chunks]
            )

            prepared = await load_prepared_points(db)
            point_embeddings: dict[str, list[float]] = {}
            if prepared:
                profiles = [
                    item.profile or item.point.name for item in prepared
                ]
                vectors = await embedder.embed(profiles)
                point_embeddings = {
                    item.point.id: vector
                    for item, vector in zip(prepared, vectors, strict=False)
                }

            job.progress = 0.65
            job.message = "知识点打标"
            await db.commit()

            tagged = [
                TaggedChunk(
                    content=item.content,
                    heading=item.heading,
                    heading_path=item.heading_path,
                    page=item.page,
                    time_start=item.time_start,
                    time_end=item.time_end,
                    frame_path=item.frame_path,
                    page_image_path=item.page_image_path,
                    tag=tag_text_multi(
                        item.content,
                        prepared,
                        heading=item.heading_path or item.heading,
                        embedding=vector,
                        point_embeddings=point_embeddings,
                    ),
                )
                for item, vector in zip(raw_chunks, embeddings, strict=False)
            ]

            job.progress = 0.8
            job.message = "写入索引"
            await db.commit()

            count = await replace_chunks(
                db, material, tagged, embeddings, embedder.name
            )

            extraction = {
                "units": 0,
                "skills": 0,
                "new_skills": 0,
                "proposals": 0,
                "model": "",
                "warning": "",
            }
            if settings.enable_knowledge_extraction:
                job.progress = 0.9
                job.message = "抽取知识单元"
                await db.commit()
                try:
                    extraction = await extract_material_units(
                        db, material.id, llm
                    )
                except Exception as exc:
                    logger.exception("knowledge extraction failed")
                    extraction["warning"] = (
                        f"知识抽取失败：{str(exc)[:180]}"
                    )

            question_result = {"questions": 0, "model": "", "warning": ""}
            job.progress = 0.95
            job.message = "识别题目"
            await db.commit()

            async def _question_progress(done: int, total: int) -> None:
                job.progress = 0.95 + 0.04 * (done / max(total, 1))
                job.message = f"识别题目 {done}/{total} 批"
                await db.commit()

            try:
                question_result = await extract_questions(
                    db, material.id, llm, progress=_question_progress
                )
            except Exception as exc:
                logger.exception("question extraction failed")
                question_result["warning"] = f"题目识别失败：{str(exc)[:150]}"

            material.status = "ready"
            material.error = ""
            job.status = "done"
            job.progress = 1.0
            warnings = [
                item
                for item in (parsed.warning, extraction.get("warning", ""))
                if item
            ]
            slide_count = len(slide_items or [])
            job.message = (
                f"已索引 {count} 个分块，抽取 {extraction['units']} 个知识单元。"
                + (
                    f" 发现 {extraction['proposals']} 个新知识点候选。"
                    if extraction.get("proposals")
                    else ""
                )
                + (f" 视频幻灯片 {slide_count} 页。" if slide_count else "")
                + (
                    f" 识别 {question_result['questions']} 道题目。"
                    if question_result.get("questions")
                    else ""
                )
                + (
                    f" {rendered_count} 页已保留原页图片。"
                    if rendered_count
                    else ""
                )
                + (" " + " ".join(warnings) if warnings else "")
            )
            ocr_pages = drain_ocr_pages()
            asr_seconds = drain_asr_seconds()
            summary_prompt, summary_completion = drain_summary_usage()
            try:
                if ocr_pages:
                    await record_service_usage(
                        db,
                        user_id=settings.default_user_id,
                        service="ocr",
                        provider="deepseek",
                        units=ocr_pages,
                        llm=llm,
                    )
                if asr_seconds:
                    await record_service_usage(
                        db,
                        user_id=settings.default_user_id,
                        service="asr",
                        provider="deepseek",
                        units=asr_seconds,
                        llm=llm,
                    )
                if summary_prompt or summary_completion:
                    await record_usage(
                        db,
                        user_id=settings.default_user_id,
                        session_id="",
                        role="knowledge",
                        model=role_model_config(llm, "knowledge").model,
                        prompt_tokens=summary_prompt,
                        completion_tokens=summary_completion,
                        llm=llm,
                        api_base=role_model_config(llm, "knowledge").api_base,
                    )
            except Exception:
                logger.exception("failed to record ingestion usage")

            job.result_json = json.dumps(
                {
                    "chunk_count": count,
                    "video_slides": slide_count,
                    "embedding_model": embedder.name,
                    "knowledge_units": extraction["units"],
                    "knowledge_proposals": extraction.get("proposals", 0),
                    "skills": extraction["skills"],
                    "new_skills": extraction["new_skills"],
                    "extraction_model": extraction.get("model", ""),
                    "warning": parsed.warning,
                    "extraction_warning": extraction.get("warning", ""),
                    "ocr_pages": ocr_pages,
                    "asr_seconds": round(asr_seconds, 1),
                    "questions": question_result.get("questions", 0),
                    "question_warning": question_result.get("warning", ""),
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
    clear_frames(material_id)
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
    await db.execute(
        delete(KnowledgeUnit).where(KnowledgeUnit.material_id == material_id)
    )
    await db.delete(material)
    await db.commit()

    folder = UPLOAD_DIR / material_id
    if folder.exists():
        await asyncio.to_thread(shutil.rmtree, folder, True)
    clear_frames(material_id)
    return True


async def latest_job_for_material(db: AsyncSession, material_id: str) -> Job | None:
    result = await db.execute(
        select(Job)
        .where(Job.type == "ingest", Job.payload_json.contains(material_id))
        .order_by(Job.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
