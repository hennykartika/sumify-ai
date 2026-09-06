"""Pipeline utama: transkrip -> ringkasan -> PDF, sambil memperbarui status DB.

Dijalankan sinkron di dalam request (belum lewat Celery). Begitu Redis tersedia,
fungsi `summarize_and_generate_pdf` tinggal dipanggil dari task worker.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from src.core.database.postgree import async_session_maker
from src.core.logging.logger import get_logger
from src.repositories import (
    MeetingRepository,
    SummaryRepository,
    TranscriptionRepository,
)
from src.schemas.common import ProcessingStatus
from src.services.pdf_generator.pdf_generator_service import PDFGeneratorService
from src.services.storage.storage import storage_service
from src.services.summary_generator import get_summary_service

logger = get_logger(__name__)


class PipelineError(Exception):
    """Pipeline gagal di salah satu tahap."""


@dataclass
class PipelineResult:
    meeting_id: int
    template_type: str
    pdf_path: str
    pdf_url: str | None
    summary_id: int


async def summarize_and_generate_pdf(
    meeting_id: int,
    template_type: str = "simple",
    upload_pdf: bool = True,
) -> PipelineResult:
    """Ambil transkrip meeting, ringkas dengan LLM, lalu hasilkan PDF.

    Prasyarat: meeting sudah punya transcription. Kalau belum ada, angkat error.
    """
    async with async_session_maker() as session:
        meeting_repo = MeetingRepository(session)
        transcription_repo = TranscriptionRepository(session)
        summary_repo = SummaryRepository(session)

        meeting = await meeting_repo.get_by_id(meeting_id)
        if meeting is None:
            raise PipelineError(f"Meeting {meeting_id} tidak ditemukan")

        transcription = await transcription_repo.get_by_meeting_id(meeting_id)
        if transcription is None or not (transcription.full_text or "").strip():
            raise PipelineError(
                f"Meeting {meeting_id} belum punya transkrip. "
                "Jalankan transkripsi lebih dulu."
            )

        audio_filename = Path(meeting.storage_path or "").name or None

        # ── Tahap 1: ringkasan ──
        await meeting_repo.update_status(meeting_id, ProcessingStatus.SUMMARIZING)

        try:
            result = await get_summary_service().generate(
                transcript=transcription.full_text,
                template_type=template_type,
                audio_filename=audio_filename,
                language=meeting.language or "id",
            )
        except Exception as exc:
            await meeting_repo.update_status(meeting_id, ProcessingStatus.FAILED)
            logger.error(f"Ringkasan gagal untuk meeting {meeting_id}: {exc}")
            raise PipelineError(f"Gagal membuat ringkasan: {exc}") from exc

        existing = await summary_repo.get_by_meeting_id(meeting_id)
        summary_values = {
            "summary": result.summary_text,
            "key_points": result.key_points,
            "action_items": result.action_items,
            "decisions": result.decisions,
        }

        if existing is None:
            summary_row = await summary_repo.create(
                meeting_id=meeting_id, **summary_values
            )
        else:
            summary_row = await summary_repo.update(existing.id, **summary_values)

        # ── Tahap 2: PDF ──
        await meeting_repo.update_status(meeting_id, ProcessingStatus.GENERATING_PDF)

        try:
            pdf_path = await asyncio.to_thread(
                PDFGeneratorService().generate_pdf,
                result.pdf_template,
                result.context,
                f"meeting-{meeting_id}-{result.template_type}.pdf",
            )
        except Exception as exc:
            await meeting_repo.update_status(meeting_id, ProcessingStatus.FAILED)
            logger.error(f"PDF gagal untuk meeting {meeting_id}: {exc}")
            raise PipelineError(f"Gagal membuat PDF: {exc}") from exc

        # ── Tahap 3: simpan PDF ke storage (opsional) ──
        pdf_url: str | None = None
        if upload_pdf:
            try:
                info = await storage_service.upload_pdf(
                    file_data=Path(pdf_path).read_bytes(),
                    meeting_id=meeting_id,
                    filename=Path(pdf_path).name,
                )
                pdf_url = await storage_service.get_file_url(info.storage_path)
                await meeting_repo.update(meeting_id, pdf_url=info.storage_path)
            except Exception as exc:
                logger.warning(
                    f"PDF meeting {meeting_id} jadi tapi gagal diunggah: {exc}"
                )

        await meeting_repo.update_status(meeting_id, ProcessingStatus.COMPLETED)
        logger.info(f"Pipeline selesai untuk meeting {meeting_id}: {pdf_path}")

        return PipelineResult(
            meeting_id=meeting_id,
            template_type=result.template_type,
            pdf_path=str(pdf_path),
            pdf_url=pdf_url,
            summary_id=summary_row.id,
        )