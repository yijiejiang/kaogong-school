import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.rag.asr import (
    AUDIO_SUFFIXES,
    AsrError,
    AsrUnavailable,
    asr_status,
    transcribe_file,
)
from app.rag.parsers import sanitize_filename
from app.services.settings_service import load_llm_settings

router = APIRouter(prefix="/api/asr", tags=["asr"])

MAX_ASR_BYTES = 25 * 1024 * 1024


@router.get("/status")
async def status(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    llm = await load_llm_settings(db)
    return asr_status(llm)


@router.post("/transcribe")
async def transcribe(
    file: Annotated[UploadFile, File(...)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    filename = sanitize_filename(file.filename or "audio.m4a")
    suffix = Path(filename).suffix.lower()
    if suffix not in AUDIO_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail="支持 mp3、m4a、wav、aac、flac、ogg、webm、mp4 音频。",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="音频为空。")
    if len(data) > MAX_ASR_BYTES:
        raise HTTPException(status_code=400, detail="音频超过 25 MB 上限。")

    llm = await load_llm_settings(db)
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / filename
        path.write_bytes(data)
        try:
            result = await transcribe_file(path, llm, filename=filename)
        except AsrUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except AsrError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "text": result.text,
        "provider": result.provider,
        "model": result.model,
        "chars": len(result.text),
    }
