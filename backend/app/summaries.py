"""AI summaries for uploaded PDFs.

When a PDF lands on a note the file is read back, its text is extracted, and a
short summary is requested from OpenRouter (any OpenAI-compatible chat
endpoint). The result is stored on the attachment row, so both clients render
it with the file instead of behind a button. Without an `OPENROUTER_API_KEY`
the upload still succeeds and the attachment is marked `skipped`.
"""

from __future__ import annotations

import logging
from io import BytesIO

import httpx

from . import services
from .config import settings
from .database import SessionLocal
from .models import Attachment

logger = logging.getLogger("studyhub")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
PAGES_READ_LIMIT = 60

SUMMARY_PROMPT = (
    "You are summarising study material for a student. In at most 120 words, "
    "say what this document covers and list the key topics worth revising. "
    "Plain text only: no markdown headings, no bullet characters."
)


def extract_pdf_text(data: bytes, max_chars: int) -> str:
    """Best-effort text extraction; scanned PDFs simply come back empty."""
    from pypdf import PdfReader  # lazy: only uploads need the dependency

    reader = PdfReader(BytesIO(data))
    chunks: list[str] = []
    total = 0
    for page in reader.pages:
        text = page.extract_text() or ""
        chunks.append(text)
        total += len(text)
        if total >= max_chars or len(chunks) >= PAGES_READ_LIMIT:
            break
    return "\n".join(chunks)[:max_chars]


async def _ask_openrouter(text: str) -> str:
    payload = {
        "model": settings.summary_model,
        "messages": [
            {"role": "system", "content": SUMMARY_PROMPT},
            {"role": "user", "content": text},
        ],
        "max_tokens": settings.summary_max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        # OpenRouter asks clients to identify themselves.
        "HTTP-Referer": "https://studyhub.local",
        "X-Title": settings.project_name,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(OPENROUTER_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
    content = data["choices"][0]["message"]["content"]
    summary = (content or "").strip()
    if not summary:
        raise ValueError("model returned an empty summary")
    return summary[:4000]


async def summarize_attachment(attachment_id: int) -> None:
    """Background task: fill `summary` / `summary_status` for one attachment."""
    db = SessionLocal()
    try:
        attachment = db.get(Attachment, attachment_id)
        if attachment is None:
            return
        if attachment.content_type != "application/pdf":
            attachment.summary_status = "skipped"
            db.commit()
            return
        if not settings.openrouter_api_key:
            attachment.summary_status = "skipped"
            db.commit()
            return

        attachment.summary_status = "pending"
        db.commit()

        try:
            text = extract_pdf_text(
                services.read_file(attachment.storage_key),
                settings.summary_max_chars,
            )
            if not text.strip():
                raise ValueError("no selectable text in the PDF")
            summary = await _ask_openrouter(text)
        except Exception as exc:  # any failure is recorded, never raised
            logger.warning("summary failed for attachment %s: %s", attachment_id, exc)
            attachment.summary_status = "failed"
            attachment.summary = None
            db.commit()
            return

        attachment.summary = summary
        attachment.summary_status = "ready"
        db.commit()
    finally:
        db.close()
