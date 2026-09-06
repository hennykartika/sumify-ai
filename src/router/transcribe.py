"""Router untuk transkripsi otomatis dengan Whisper."""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException

from src.core.database.postgree import async_session_maker
from src.core.logging.logger import get_logger
from src.repositories import MeetingRepository, TranscriptionRepository
from src.schemas.common import ProcessingStatus
from src.services.storage.storage import storage_service
from src.services.transcriber import TranscriptionError, get_transcriber

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["transcribe"])


@router.post("/meetings/{meeting_id}/transcribe")
async def transcribe_meeting(meeting_id: int, language: str | None = Form(None)):
    """Unduh audio meeting dari storage lalu transkripsikan dengan Whisper.

    Pemanggilan pertama akan mengunduh model Whisper (~150 MB untuk 'base'),
    jadi bisa memakan waktu beberapa menit. Pemanggilan berikutnya lebih cepat
    karena model sudah tersimpan di cache.
    """
    async with async_session_maker() as session:
        meeting_repo = MeetingRepository(session)
        meeting = await meeting_repo.get_by_id(meeting_id)

        if meeting is None:
            raise HTTPException(status_code=404, detail="Meeting tidak ditemukan")
        if not meeting.storage_path:
            raise HTTPException(
                status_code=422, detail="Meeting ini tidak punya berkas audio"
            )

        await meeting_repo.update_status(meeting_id, ProcessingStatus.TRANSCRIBING)

    tmp_path: Path | None = None

    try:
        # Whisper membaca dari disk, jadi audio diunduh ke berkas sementara.
        audio_bytes = await storage_service.download_file(meeting.storage_path)
        suffix = Path(meeting.storage_path).suffix or ".mp3"

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(audio_bytes)
            tmp_path = Path(tmp.name)

        result = await get_transcriber().transcribe(
            tmp_path, language=language or meeting.language or None
        )
    except TranscriptionError as exc:
        async with async_session_maker() as session:
            await MeetingRepository(session).update_status(
                meeting_id, ProcessingStatus.FAILED
            )
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        async with async_session_maker() as session:
            await MeetingRepository(session).update_status(
                meeting_id, ProcessingStatus.FAILED
            )
        logger.error(f"Transkripsi meeting {meeting_id} gagal: {exc}")
        raise HTTPException(status_code=500, detail=f"Transkripsi gagal: {exc}") from exc
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    async with async_session_maker() as session:
        transcription_repo = TranscriptionRepository(session)
        values = {
            "full_text": result.full_text,
            "segments": result.segments,
            "language": result.language,
        }

        existing = await transcription_repo.get_by_meeting_id(meeting_id)
        if existing is None:
            row = await transcription_repo.create(meeting_id=meeting_id, **values)
        else:
            row = await transcription_repo.update(existing.id, **values)

        await MeetingRepository(session).update_status(
            meeting_id, ProcessingStatus.UPLOADED
        )

    return {
        "message": "Transkripsi selesai",
        "meeting_id": meeting_id,
        "transcription_id": row.id,
        "language": result.language,
        "duration": result.duration_label,
        "segments": len(result.segments),
        "length": len(result.full_text),
        "preview": result.full_text[:300],
    }