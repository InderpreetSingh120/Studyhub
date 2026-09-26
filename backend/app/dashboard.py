"""Home-screen aggregates: one request that fills the dashboard of either client.

Everything except "my groups" describes the whole gallery, because the gallery
belongs to everyone. Every number is derived on the server so the web and
Android apps render the same figures without paging through the note list.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .auth import get_current_user
from .database import get_db
from .groups import _member_counts
from .models import (
    KIND_LABELS,
    NOTE_KINDS,
    SEMESTER_MAX,
    SEMESTER_MIN,
    Group,
    GroupMember,
    Message,
    Note,
    Subject,
    User,
    utcnow,
)
from .schemas import (
    DashboardGroup,
    DashboardNote,
    DashboardNotes,
    DashboardOut,
    LabelCount,
    MessagePreview,
    SubjectCount,
    TrendPoint,
)

dashboard_router = APIRouter(prefix="/dashboard", tags=["dashboard"])

RECENT_NOTES = 5
TREND_DAYS = 30


def _label_counts(rows: list[tuple[str, int]], labels: dict[str, str] | None = None):
    """Turn `(key, count)` rows into ordered `LabelCount`s."""
    return [
        LabelCount(
            key=key,
            label=(labels or {}).get(key, key),
            count=count,
        )
        for key, count in rows
    ]


def _note_summary(db: Session) -> DashboardNotes:
    def count(*extra) -> int:
        stmt = select(func.count()).select_from(Note)
        return db.scalar(stmt.where(*extra)) or 0

    subject_rows = db.execute(
        select(Subject.id, Subject.name, Subject.color, func.count(Note.id))
        .select_from(Subject)
        .outerjoin(Note, Note.subject_id == Subject.id)
        .group_by(Subject.id, Subject.name, Subject.color)
    ).all()
    by_subject = [
        SubjectCount(subject_id=subject_id, name=name, color=color, count=total)
        for subject_id, name, color, total in subject_rows
    ]
    by_subject.sort(key=lambda item: item.name.lower())

    by_kind = _label_counts(
        db.execute(
            select(Note.kind, func.count(Note.id))
            .group_by(Note.kind)
            .order_by(func.count(Note.id).desc(), Note.kind)
        ).all(),
        KIND_LABELS,
    )

    by_branch = _label_counts(
        db.execute(
            select(Note.branch, func.count(Note.id))
            .group_by(Note.branch)
            .order_by(func.count(Note.id).desc(), Note.branch)
        ).all()
    )

    semester_rows = dict(
        db.execute(
            select(Note.semester, func.count(Note.id)).group_by(Note.semester)
        ).all()
    )
    by_semester = [
        LabelCount(
            key=str(semester),
            label=f"Semester {semester}",
            count=semester_rows.get(semester, 0),
        )
        for semester in range(SEMESTER_MIN, SEMESTER_MAX + 1)
    ]

    return DashboardNotes(
        total=count(),
        done=count(Note.is_done.is_(True)),
        without_subject=count(Note.subject_id.is_(None)),
        by_subject=by_subject,
        by_kind=by_kind,
        by_branch=by_branch,
        by_semester=by_semester,
    )


def _recent_notes(db: Session) -> list[DashboardNote]:
    rows = db.execute(
        select(Note, User.username)
        .join(User, User.id == Note.owner_id)
        .order_by(Note.updated_at.desc(), Note.id.desc())
        .limit(RECENT_NOTES)
    ).all()
    return [
        DashboardNote(
            id=note.id,
            title=note.title,
            author=username,
            subject_id=note.subject_id,
            semester=note.semester,
            branch=note.branch,
            kind=note.kind,
            is_done=note.is_done,
            updated_at=note.updated_at,
        )
        for note, username in rows
    ]


def _last_messages(db: Session, group_ids: list[int]) -> dict[int, MessagePreview]:
    latest = dict(
        db.execute(
            select(Message.group_id, func.max(Message.id))
            .where(Message.group_id.in_(group_ids))
            .group_by(Message.group_id)
        ).all()
    )
    if not latest:
        return {}
    rows = db.execute(
        select(Message, User.username)
        .join(User, User.id == Message.sender_id)
        .where(Message.id.in_(latest.values()))
    ).all()
    return {
        message.group_id: MessagePreview(
            sender=username, body=message.body, created_at=message.created_at
        )
        for message, username in rows
    }


def _groups(db: Session, user: User) -> list[DashboardGroup]:
    rows = db.execute(
        select(Group)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .where(GroupMember.user_id == user.id)
    ).all()
    groups = [group for (group,) in rows]
    groups.sort(key=lambda group: group.name.lower())
    if not groups:
        return []

    ids = [group.id for group in groups]
    counts = _member_counts(db, ids)
    previews = _last_messages(db, ids)
    return [
        DashboardGroup(
            id=group.id,
            name=group.name,
            member_count=counts.get(group.id, 0),
            last_message=previews.get(group.id),
        )
        for group in groups
    ]


def _trend(db: Session) -> list[TrendPoint]:
    """Notes created per day over the last 30 days, zero-filled for charting.

    The dates are counted in Python instead of in SQL so the same query works
    on SQLite and PostgreSQL without a dialect branch.
    """
    cutoff_day = (utcnow() - timedelta(days=TREND_DAYS - 1)).date()
    cutoff = datetime.combine(cutoff_day, time.min)
    stamps = db.scalars(select(Note.created_at).where(Note.created_at >= cutoff))
    per_day = Counter(stamp.date() for stamp in stamps)

    points = []
    for offset in range(TREND_DAYS):
        day = cutoff_day + timedelta(offset)
        points.append(TrendPoint(date=day.isoformat(), count=per_day.get(day, 0)))
    return points


@dashboard_router.get("", response_model=DashboardOut, summary="Home screen aggregates")
def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardOut:
    return DashboardOut(
        notes=_note_summary(db),
        recent_notes=_recent_notes(db),
        groups=_groups(db, current_user),
        trend=_trend(db),
    )
