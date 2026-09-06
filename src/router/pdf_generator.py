"""Router untuk membuat ulang PDF dari ringkasan yang sudah tersimpan.

Berguna kalau template diperbarui dan PDF lama perlu dicetak ulang tanpa
memanggil LLM lagi (hemat kuota).
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException

from src.core.database.postgree import async_session_maker
from src.core.logging.logger import get_logger
from src.prompts.prompt_handler import build_prompt
from src.repositories import MeetingRepository, SummaryRepository
from src.services.pdf_generator.pdf_generator_service import PDFGeneratorService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["pdf"])


@router.post("/meetings/{meeting_id}/regenerate-pdf")
async def regenerate_pdf(meeting_id: int, template_type: str = Form("simple")):
    """Cetak ulang PDF memakai ringkasan yang sudah ada di database."""
    async with async_session_maker() as session:
        meeting = await MeetingRepository(session).get_by_id(meeting_id)
        if meeting is None:
            raise HTTPException(status_code=404, detail="Meeting tidak ditemukan")

        summary = await SummaryRepository(session).get_by_meeting_id(meeting_id)
        if summary is None:
            raise HTTPException(
                status_code=404,
                detail="Meeting ini belum punya ringkasan. Jalankan /summarize dulu.",
            )

    try:
        spec = build_prompt(template_type, "placeholder")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    language_label = {"id": "Indonesia", "en": "English"}.get(
        meeting.language or "id", meeting.language or "-"
    )
    audio_filename = (
        meeting.description or Path(meeting.storage_path or "").name or "-"
    )

    context = {
        "title": meeting.title or "Ringkasan Rapat",
        "audio_filename": audio_filename,
        "generated_date": datetime.now().strftime("%d %B %Y"),
        "language": language_label,
        "duration": "-",
    }

    # Ringkasan disimpan netral di DB, dipetakan ulang sesuai template tujuan.
    if spec.pdf_template == "business":
        context.update(
            {
                "executive_summary": summary.summary or "",
                "key_discussion_points": summary.key_points or [],
                "decisions": summary.decisions or [],
                "next_steps": [],
                "action_assignment": summary.action_items or [],
            }
        )
    else:
        context.update(
            {
                "summary": summary.summary or "",
                "key_points": summary.key_points or [],
                "keywords": [],
                "action_items": summary.action_items or [],
            }
        )

    try:
        pdf_path = await asyncio.to_thread(
            PDFGeneratorService().generate_pdf,
            spec.pdf_template,
            context,
            f"meeting-{meeting_id}-{spec.template_type}.pdf",
        )
    except Exception as exc:
        logger.error(f"Regenerate PDF gagal untuk meeting {meeting_id}: {exc}")
        raise HTTPException(status_code=500, detail=f"Gagal membuat PDF: {exc}") from exc

    return {
        "message": "PDF dibuat ulang dari ringkasan tersimpan",
        "meeting_id": meeting_id,
        "template_type": spec.template_type,
        "pdf_path": str(pdf_path),
    }