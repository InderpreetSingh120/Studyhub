"""Subject, note and attachment endpoints.

Notes are a public gallery: every logged-in user reads every note, and the
uploader's name travels with it. Writing stays private — only the owner (or
an admin) may change or delete a note. Subjects are a shared syllabus list.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import services, summaries
from .auth import get_current_user
from .database import get_db
from .models import NOTE_KINDS, KIND_LABELS, Attachment, Note, Subject, User
from .schemas import (
    AttachmentOut,
    NoteIn,
    NoteOut,
    NoteUpdate,
    SubjectIn,
    SubjectOut,
    SubjectUpdate,
)

subjects_router = APIRouter(prefix="/subjects", tags=["subjects"])
notes_router = APIRouter(prefix="/notes", tags=["notes"])

# The only uploads this app accepts: PDFs and images.
ALLOWED_UPLOAD_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _is_admin(user: User) -> bool:
    return user.role == "admin"


def _note_for_read(note_id: int, db: Session) -> Note:
    """The gallery is public: any note that exists can be read."""
    note = db.get(Note, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


def _note_for_write(note_id: int, user: User, db: Session) -> Note:
    note = _note_for_read(note_id, db)
    if note.owner_id != user.id and not _is_admin(user):
        raise HTTPException(status_code=403, detail="You can only change your own notes")
    return note


def _subject_for_write(subject_id: int, user: User, db: Session) -> Subject:
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise HTTPException(status_code=404, detail="Subject not found")
    if subject.created_by != user.id and not _is_admin(user):
        raise HTTPException(
            status_code=403, detail="Only the creator or an admin can change this subject"
        )
    return subject


def _ensure_subject(subject_id: int, db: Session) -> None:
    if db.get(Subject, subject_id) is None:
        raise HTTPException(status_code=400, detail="Unknown subject")


def _contains(term: str) -> str:
    """Escape LIKE wildcards so a literal `%` in a query stays literal."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _note_out(note: Note, author: str, attachment_count: int = 0) -> NoteOut:
    return NoteOut(
        id=note.id,
        title=note.title,
        body=note.body,
        subject_id=note.subject_id,
        semester=note.semester,
        branch=note.branch,
        kind=note.kind,
        kind_label=KIND_LABELS.get(note.kind, note.kind),
        is_done=note.is_done,
        author_id=note.owner_id,
        author=author,
        attachment_count=attachment_count,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


def _upload_content_type(file: UploadFile) -> str:
    """Allowed MIME type for an upload, falling back to the file extension.

    Several clients (Android's, and anything reading from disk) send
    `application/octet-stream` instead of the real type, so the extension
    decides in that case.
    """
    allowed = ", ".join(sorted(ALLOWED_UPLOAD_TYPES))
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type in ALLOWED_UPLOAD_TYPES:
        return content_type

    if content_type in ("", "application/octet-stream"):
        suffix = Path(services.safe_filename(file.filename or "")).suffix.lower()
        suffix = ".jpg" if suffix == ".jpeg" else suffix
        for candidate, extension in ALLOWED_UPLOAD_TYPES.items():
            if extension == suffix:
                return candidate

    raise HTTPException(status_code=415, detail=f"Unsupported file type; allowed: {allowed}")


# --- subjects (shared syllabus topics) --------------------------------------


@subjects_router.get("", response_model=list[SubjectOut], summary="List subjects")
def list_subjects(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Subject]:
    return list(
        db.scalars(select(Subject).order_by(func.lower(Subject.name), Subject.id))
    )


@subjects_router.post("", response_model=SubjectOut, status_code=201, summary="Create subject")
def create_subject(
    payload: SubjectIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Subject:
    duplicate = db.scalar(
        select(Subject).where(func.lower(Subject.name) == payload.name.lower())
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="This subject already exists")

    subject = Subject(name=payload.name, color=payload.color, created_by=current_user.id)
    db.add(subject)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="This subject already exists") from exc
    db.refresh(subject)
    return subject


@subjects_router.patch("/{subject_id}", response_model=SubjectOut, summary="Update subject")
def update_subject(
    subject_id: int,
    payload: SubjectUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Subject:
    subject = _subject_for_write(subject_id, current_user, db)
    data = payload.model_dump(exclude_unset=True)

    if "name" in data and data["name"].lower() != subject.name.lower():
        duplicate = db.scalar(
            select(Subject).where(
                func.lower(Subject.name) == data["name"].lower(),
                Subject.id != subject.id,
            )
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="This subject already exists")

    for field, value in data.items():
        setattr(subject, field, value)
    db.commit()
    db.refresh(subject)
    return subject


@subjects_router.delete("/{subject_id}", status_code=204, summary="Delete subject")
def delete_subject(
    subject_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    subject = _subject_for_write(subject_id, current_user, db)
    db.delete(subject)  # notes keep their text, subject_id becomes NULL
    db.commit()


# --- notes (the public gallery) ---------------------------------------------


@notes_router.get("", response_model=list[NoteOut], summary="Browse the gallery")
def list_notes(
    q: str | None = Query(None, max_length=200, description="Matches title or body"),
    subject_id: int | None = None,
    semester: int | None = Query(None, ge=1, le=8),
    branch: str | None = Query(None, max_length=40),
    kind: str | None = Query(None, max_length=10, description="notes|practical|mst|final"),
    mine: bool | None = Query(None, description="true = only my uploads"),
    done: bool | None = None,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[NoteOut]:
    if kind is not None and kind.lower() not in NOTE_KINDS:
        raise HTTPException(
            status_code=400, detail=f"kind must be one of {', '.join(NOTE_KINDS)}"
        )

    statement = (
        select(Note, User.username, func.count(Attachment.id))
        .join(User, User.id == Note.owner_id)
        .outerjoin(Attachment, Attachment.note_id == Note.id)
    )

    if q:
        pattern = _contains(q)
        statement = statement.where(
            or_(Note.title.ilike(pattern, escape="\\"), Note.body.ilike(pattern, escape="\\"))
        )
    if subject_id is not None:
        statement = statement.where(Note.subject_id == subject_id)
    if semester is not None:
        statement = statement.where(Note.semester == semester)
    if branch:
        statement = statement.where(func.lower(Note.branch) == branch.strip().lower())
    if kind:
        statement = statement.where(Note.kind == kind.lower())
    if mine:
        statement = statement.where(Note.owner_id == current_user.id)
    if done is not None:
        statement = statement.where(Note.is_done == done)

    rows = db.execute(
        statement.group_by(Note.id, User.username)
        .order_by(Note.updated_at.desc(), Note.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [_note_out(note, username, count) for note, username, count in rows]


@notes_router.post("", response_model=NoteOut, status_code=201, summary="Upload a note")
def create_note(
    payload: NoteIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NoteOut:
    if payload.subject_id is not None:
        _ensure_subject(payload.subject_id, db)

    note = Note(
        owner_id=current_user.id,
        subject_id=payload.subject_id,
        title=payload.title,
        body=payload.body,
        semester=payload.semester,
        branch=payload.branch,
        kind=payload.kind,
        is_done=payload.is_done,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return _note_out(note, current_user.username)


@notes_router.get("/{note_id}", response_model=NoteOut, summary="Read a note")
def get_note(
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NoteOut:
    note = _note_for_read(note_id, db)
    author = db.get(User, note.owner_id)
    count = db.scalar(
        select(func.count()).select_from(Attachment).where(Attachment.note_id == note.id)
    )
    return _note_out(note, author.username if author else "", count or 0)


@notes_router.patch("/{note_id}", response_model=NoteOut, summary="Update a note")
def update_note(
    note_id: int,
    payload: NoteUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NoteOut:
    note = _note_for_write(note_id, current_user, db)
    data = payload.model_dump(exclude_unset=True)

    if data.get("subject_id") is not None:
        _ensure_subject(data["subject_id"], db)

    for field, value in data.items():
        setattr(note, field, value)
    db.commit()
    db.refresh(note)
    author = db.get(User, note.owner_id)
    return _note_out(note, author.username if author else "")


@notes_router.delete("/{note_id}", status_code=204, summary="Delete a note")
def delete_note(
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    note = _note_for_write(note_id, current_user, db)
    for attachment in list(note.attachments):
        services.delete_file(attachment.storage_key)
    db.delete(note)  # attachment rows go with it (ORM cascade)
    db.commit()


# --- attachments (public files, AI summaries for PDFs) -----------------------


@notes_router.post(
    "/{note_id}/attachments",
    response_model=AttachmentOut,
    status_code=201,
    summary="Upload PDF or image",
)
def upload_attachment(
    note_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Attachment:
    note = _note_for_write(note_id, current_user, db)

    content_type = _upload_content_type(file)

    key = f"{note.id}/{uuid4().hex}{ALLOWED_UPLOAD_TYPES[content_type]}"
    attachment = Attachment(
        note_id=note.id,
        storage_key=key,
        filename=services.safe_filename(file.filename or "file"),
        content_type=content_type,
        size_bytes=0,
        summary_status="pending",
    )
    try:
        attachment.size_bytes = services.save_file(key, file.file, content_type)
    except services.FileTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc

    db.add(attachment)
    try:
        db.commit()
    except IntegrityError as exc:  # note vanished mid-upload: do not leak the file
        db.rollback()
        services.delete_file(key)
        raise HTTPException(status_code=404, detail="Note not found") from exc
    db.refresh(attachment)

    # Summaries are made automatically, right after the file is stored.
    background_tasks.add_task(summaries.summarize_attachment, attachment.id)
    return attachment


@notes_router.get(
    "/{note_id}/attachments",
    response_model=list[AttachmentOut],
    summary="List attachments",
)
def list_attachments(
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Attachment]:
    note = _note_for_read(note_id, db)
    return list(
        db.scalars(
            select(Attachment)
            .where(Attachment.note_id == note.id)
            .order_by(Attachment.id)
        )
    )


@notes_router.get(
    "/{note_id}/attachments/{attachment_id}", summary="Download attachment"
)
def download_attachment(
    note_id: int,
    attachment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    note = _note_for_read(note_id, db)
    attachment = db.scalar(
        select(Attachment).where(
            Attachment.id == attachment_id, Attachment.note_id == note.id
        )
    )
    if attachment is None:
        raise HTTPException(status_code=404, detail="Attachment not found")

    url = services.download_url(attachment.storage_key)
    if url:
        return RedirectResponse(url, status_code=302)

    path = services.local_path(attachment.storage_key)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Attachment file is missing")
    return FileResponse(path, media_type=attachment.content_type, filename=attachment.filename)


@notes_router.delete(
    "/{note_id}/attachments/{attachment_id}", status_code=204, summary="Delete attachment"
)
def delete_attachment(
    note_id: int,
    attachment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    note = _note_for_write(note_id, current_user, db)
    attachment = db.scalar(
        select(Attachment).where(
            Attachment.id == attachment_id, Attachment.note_id == note.id
        )
    )
    if attachment is None:
        raise HTTPException(status_code=404, detail="Attachment not found")

    services.delete_file(attachment.storage_key)
    db.delete(attachment)
    db.commit()
