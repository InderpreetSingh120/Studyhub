from __future__ import annotations

import asyncio
from io import BytesIO

from app import summaries
from app.config import settings

PDF = b"%PDF-1.4\n%%EOF\n"
IMAGE = b"\x89PNG\r\n\x1a\n"


def create_note(client, headers):
    response = client.post(
        "/api/notes",
        headers=headers,
        json={
            "title": "Physics",
            "body": "",
            "semester": 4,
            "branch": "CSE",
            "kind": "notes",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def upload(client, headers, note_id, data=PDF, name="book.pdf", content_type="application/pdf"):
    response = client.post(
        f"/api/notes/{note_id}/attachments",
        headers=headers,
        files={"file": (name, data, content_type)},
    )
    assert response.status_code == 201, response.text
    return response.json()


def listed(client, headers, note_id) -> list:
    response = client.get(f"/api/notes/{note_id}/attachments", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def blank_pdf() -> bytes:
    """A valid PDF with no extractable text (one empty page)."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_without_an_api_key_the_upload_is_marked_skipped(client, alice, monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    note = create_note(client, alice)

    upload(client, alice, note["id"])

    attachment = listed(client, alice, note["id"])[0]
    assert attachment["summary_status"] == "skipped"
    assert attachment["summary"] is None


def test_a_summary_is_stored_as_soon_as_the_file_lands(client, alice, monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-test-key")
    monkeypatch.setattr(
        summaries, "extract_pdf_text", lambda data, max_chars: "limits derivatives"
    )

    async def fake_ask(text):
        assert text == "limits derivatives"
        return "Covers limits, derivatives and integrals; revise the chain rule."

    monkeypatch.setattr(summaries, "_ask_openrouter", fake_ask)
    note = create_note(client, alice)

    upload(client, alice, note["id"])  # no button is pressed anywhere

    attachment = listed(client, alice, note["id"])[0]
    assert attachment["summary_status"] == "ready"
    assert attachment["summary"] == (
        "Covers limits, derivatives and integrals; revise the chain rule."
    )
    # the summary travels with the note too, for the gallery cards
    assert client.get(f"/api/notes/{note['id']}", headers=alice).json()[
        "attachment_count"
    ] == 1


def test_a_failing_model_marks_the_attachment_failed(client, alice, monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-test-key")
    monkeypatch.setattr(
        summaries, "extract_pdf_text", lambda data, max_chars: "some text"
    )

    async def boom(text):
        raise RuntimeError("model is down")

    monkeypatch.setattr(summaries, "_ask_openrouter", boom)
    note = create_note(client, alice)

    upload(client, alice, note["id"])

    attachment = listed(client, alice, note["id"])[0]
    assert attachment["summary_status"] == "failed"
    assert attachment["summary"] is None


def test_a_scanned_pdf_without_text_is_failed_not_hung(client, alice, monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-test-key")
    note = create_note(client, alice)

    upload(client, alice, note["id"], data=blank_pdf(), name="scan.pdf")

    attachment = listed(client, alice, note["id"])[0]
    assert attachment["summary_status"] == "failed"


def test_images_are_never_summarised(client, alice, monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-test-key")
    note = create_note(client, alice)

    upload(client, alice, note["id"], data=IMAGE, name="diagram.png", content_type="image/png")

    attachment = listed(client, alice, note["id"])[0]
    assert attachment["summary_status"] == "skipped"


def test_the_job_ignores_an_attachment_that_is_already_gone(client, alice):
    asyncio.run(summaries.summarize_attachment(4242))  # no row, no crash


def test_extract_pdf_text_returns_an_empty_string_for_a_blank_page():
    text = summaries.extract_pdf_text(blank_pdf(), max_chars=1000)

    assert text.strip() == ""
