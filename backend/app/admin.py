"""Admin moderation: users, notes and chat lines.

The gallery and both chat rooms are visible to everyone, so somebody has to be
able to clean up. These endpoints all require `role == "admin"`; the seeded
development account is `admin` (see `.env.example`).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import services
from .auth import require_admin
from .database import get_db
from .models import Attachment, GlobalMessage, Message, Note, User
from .notes import _note_out
from .schemas import AdminUserOut, AdminUserUpdate, NoteOut

admin_router = APIRouter(prefix="/admin", tags=["admin"])


def _counts(db: Session) -> tuple[dict[int, int], dict[int, int]]:
    """`(notes_by_owner, messages_by_sender)` for every user at once."""
    notes = dict(
        db.execute(
            select(Note.owner_id, func.count(Note.id)).group_by(Note.owner_id)
        ).all()
    )
    global_msgs = dict(
        db.execute(
            select(GlobalMessage.sender_id, func.count(GlobalMessage.id)).group_by(
                GlobalMessage.sender_id
            )
        ).all()
    )
    group_msgs = dict(
        db.execute(
            select(Message.sender_id, func.count(Message.id)).group_by(Message.sender_id)
        ).all()
    )
    messages = {
        user_id: global_msgs.get(user_id, 0) + group_msgs.get(user_id, 0)
        for user_id in set(global_msgs) | set(group_msgs)
    }
    return notes, messages


def _admin_user(
    user: User, notes: dict[int, int], messages: dict[int, int]
) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        username=user.username,
        phone=user.phone,
        role=user.role,
        created_at=user.created_at,
        note_count=notes.get(user.id, 0),
        message_count=messages.get(user.id, 0),
    )


def _target_user(user_id: int, db: Session) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _delete_note_files(note: Note) -> None:
    for attachment in list(note.attachments):
        services.delete_file(attachment.storage_key)


@admin_router.get("/users", response_model=list[AdminUserOut], summary="List accounts")
def list_users(
    admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> list[AdminUserOut]:
    notes, messages = _counts(db)
    users = list(db.scalars(select(User).order_by(User.created_at, User.id)))
    return [_admin_user(user, notes, messages) for user in users]


@admin_router.patch(
    "/users/{user_id}", response_model=AdminUserOut, summary="Rename an account"
)
def rename_user(
    user_id: int,
    payload: AdminUserUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminUserOut:
    user = _target_user(user_id, db)
    user.username = payload.username
    db.commit()
    db.refresh(user)
    notes, messages = _counts(db)
    return _admin_user(user, notes, messages)


@admin_router.delete("/users/{user_id}", status_code=204, summary="Delete an account")
def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    user = _target_user(user_id, db)
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    note_ids = list(db.scalars(select(Note.id).where(Note.owner_id == user.id)))
    for note_id in note_ids:
        note = db.get(Note, note_id)
        if note is not None:
            _delete_note_files(note)
    db.delete(user)  # notes, groups, memberships and messages cascade
    db.commit()


@admin_router.delete("/notes/{note_id}", status_code=204, summary="Remove a note")
def delete_any_note(
    note_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    note = db.get(Note, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    _delete_note_files(note)
    db.delete(note)
    db.commit()


@admin_router.get(
    "/notes", response_model=list[NoteOut], summary="Browse every note"
)
def list_all_notes(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[NoteOut]:
    rows = db.execute(
        select(Note, User.username, func.count(Attachment.id))
        .join(User, User.id == Note.owner_id)
        .outerjoin(Attachment, Attachment.note_id == Note.id)
        .group_by(Note.id, User.username)
        .order_by(Note.updated_at.desc(), Note.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [_note_out(note, username, count) for note, username, count in rows]


@admin_router.delete(
    "/chat/messages/{message_id}", status_code=204, summary="Remove a chat line"
)
def delete_global_message(
    message_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    message = db.get(GlobalMessage, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found")
    db.delete(message)
    db.commit()


@admin_router.delete(
    "/groups/{group_id}/messages/{message_id}",
    status_code=204,
    summary="Remove a group chat line",
)
def delete_group_message(
    group_id: int,
    message_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    message = db.scalar(
        select(Message).where(Message.id == message_id, Message.group_id == group_id)
    )
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found")
    db.delete(message)
    db.commit()
