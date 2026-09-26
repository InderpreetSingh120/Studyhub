"""Pydantic request/response models shared by both clients."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

USERNAME_RE = re.compile(r"^[A-Za-z]+(?: [A-Za-z]+)*$")
PHONE_RE = re.compile(r"^\d{10}$")
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
SEMESTER_RANGE = range(1, 9)
NOTE_KINDS = ("notes", "practical", "mst", "final")
KIND_LABELS = {
    "notes": "Notes",
    "practical": "Practical",
    "mst": "MST",
    "final": "Finals",
}


def normalize_phone(value: str) -> str:
    """Accept `9876543210`, `+91 98765 43210`, `09876543210`... → `9876543210`.

    The phone number is the unique login identifier, so every formatting a
    user might type has to collapse to the same ten digits.
    """
    digits = re.sub(r"\D", "", value.strip())
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 13 and digits.startswith("91") and digits[2] == "0":
        digits = digits[3:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if not PHONE_RE.fullmatch(digits):
        raise ValueError("phone must be a 10-digit number (optional +91 prefix)")
    return digits


def _clean_text(value: str, label: str, max_length: int) -> str:
    value = value.strip()
    if not 1 <= len(value) <= max_length:
        raise ValueError(f"{label} must be 1-{max_length} characters")
    return value


def _clean_description(value: str) -> str:
    value = value.strip()
    if len(value) > 200:
        raise ValueError("description must be at most 200 characters")
    return value


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str
    database: str
    environment: str
    version: str


# --- auth -------------------------------------------------------------------


class RegisterRequest(BaseModel):
    username: str
    phone: str
    password: str

    @field_validator("username")
    @classmethod
    def clean_username(cls, value: str) -> str:
        value = re.sub(r"\s+", " ", value.strip())
        if not USERNAME_RE.fullmatch(value):
            raise ValueError(
                "username must be 3-60 letters with single spaces between words"
            )
        if not 3 <= len(value) <= 60:
            raise ValueError("username must be 3-60 characters")
        return value

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, value: str) -> str:
        return normalize_phone(value)

    @field_validator("password")
    @classmethod
    def check_password_size(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("password must be at least 8 characters")
        if len(value.encode("utf-8")) > 72:
            # bcrypt refuses longer input; reject here instead of a 500.
            raise ValueError("password must be at most 72 bytes")
        return value


class LoginRequest(BaseModel):
    """`identifier` is a phone number or a username (when that name is unique)."""

    identifier: str
    password: str

    @field_validator("identifier")
    @classmethod
    def clean_identifier(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("phone number or username is required")
        return value


class UserOut(ORMModel):
    id: int
    username: str
    phone: str
    role: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- subjects ---------------------------------------------------------------


def _clean_color(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if not COLOR_RE.fullmatch(value):
        raise ValueError("color must be a hex color such as #3b82f6")
    return value.lower()


class SubjectIn(BaseModel):
    name: str
    color: str | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return _clean_text(value, "name", 60)

    @field_validator("color")
    @classmethod
    def clean_color(cls, value: str | None) -> str | None:
        return _clean_color(value)


class SubjectUpdate(BaseModel):
    name: str | None = None
    color: str | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("name cannot be null")
        return _clean_text(value, "name", 60)

    @field_validator("color")
    @classmethod
    def clean_color(cls, value: str | None) -> str | None:
        return _clean_color(value)


class SubjectOut(ORMModel):
    id: int
    name: str
    color: str | None
    created_by: int | None = None
    created_at: datetime


# --- notes ------------------------------------------------------------------


def _clean_semester(value: int) -> int:
    if value not in SEMESTER_RANGE:
        raise ValueError("semester must be between 1 and 8")
    return value


def _clean_branch(value: str) -> str:
    value = value.strip()
    if not 1 <= len(value) <= 40:
        raise ValueError("branch must be 1-40 characters")
    return value


def _clean_kind(value: str) -> str:
    value = value.strip().lower()
    if value not in NOTE_KINDS:
        raise ValueError(f"kind must be one of {', '.join(NOTE_KINDS)}")
    return value


class NoteIn(BaseModel):
    title: str = Field(max_length=200)
    body: str = ""
    subject_id: int | None = None
    semester: int
    branch: str
    kind: str = "notes"
    is_done: bool = False

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        return _clean_text(value, "title", 200)

    @field_validator("body")
    @classmethod
    def clean_body(cls, value: str) -> str:
        if len(value) > 100_000:
            raise ValueError("body must be at most 100000 characters")
        return value

    @field_validator("semester")
    @classmethod
    def clean_semester(cls, value: int) -> int:
        return _clean_semester(value)

    @field_validator("branch")
    @classmethod
    def clean_branch(cls, value: str) -> str:
        return _clean_branch(value)

    @field_validator("kind")
    @classmethod
    def clean_kind(cls, value: str) -> str:
        return _clean_kind(value)


class NoteUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    subject_id: int | None = None  # explicit null clears the subject
    semester: int | None = None
    branch: str | None = None
    kind: str | None = None
    is_done: bool | None = None

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("title cannot be null")
        return _clean_text(value, "title", 200)

    @field_validator("body")
    @classmethod
    def clean_body(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("body cannot be null")
        if len(value) > 100_000:
            raise ValueError("body must be at most 100000 characters")
        return value

    @field_validator("semester")
    @classmethod
    def clean_semester(cls, value: int | None) -> int | None:
        if value is None:
            raise ValueError("semester cannot be null")
        return _clean_semester(value)

    @field_validator("branch")
    @classmethod
    def clean_branch(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("branch cannot be null")
        return _clean_branch(value)

    @field_validator("kind")
    @classmethod
    def clean_kind(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("kind cannot be null")
        return _clean_kind(value)

    @field_validator("is_done")
    @classmethod
    def clean_is_done(cls, value: bool | None) -> bool:
        if value is None:
            raise ValueError("is_done cannot be null")
        return value


class NoteOut(BaseModel):
    """A gallery entry: everything both clients need to render a card."""

    id: int
    title: str
    body: str
    subject_id: int | None
    semester: int
    branch: str
    kind: str
    kind_label: str
    is_done: bool
    author_id: int
    author: str
    attachment_count: int = 0
    created_at: datetime
    updated_at: datetime


class NoteListParams(BaseModel):
    """Documented shape of `GET /api/notes` query filters (not parsed directly)."""

    q: str | None = None
    subject_id: int | None = None
    semester: int | None = None
    branch: str | None = None
    kind: str | None = None
    mine: bool | None = None
    done: bool | None = None


# --- attachments ------------------------------------------------------------


class AttachmentOut(BaseModel):
    id: int
    filename: str
    content_type: str
    size_bytes: int
    summary: str | None = None
    summary_status: str = "pending"
    created_at: datetime


# --- groups -----------------------------------------------------------------


class GroupIn(BaseModel):
    name: str
    description: str = ""

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return _clean_text(value, "name", 60)

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str) -> str:
        return _clean_description(value)


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("name cannot be null")
        return _clean_text(value, "name", 60)

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("description cannot be null")
        return _clean_description(value)


class JoinRequest(BaseModel):
    invite_code: str

    @field_validator("invite_code")
    @classmethod
    def clean_code(cls, value: str) -> str:
        value = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9]{4,8}", value):
            raise ValueError("invite code must be 4-8 letters or digits")
        return value


class GroupOut(BaseModel):
    id: int
    name: str
    description: str
    invite_code: str
    created_at: datetime
    member_count: int
    my_role: str


class GroupMemberOut(BaseModel):
    user_id: int
    username: str
    role: str
    joined_at: datetime


# --- chat --------------------------------------------------------------------


class MessageIn(BaseModel):
    body: str

    @field_validator("body")
    @classmethod
    def clean_body(cls, value: str) -> str:
        return _clean_text(value, "message", 4000)


class MessageOut(BaseModel):
    id: int
    group_id: int
    sender_id: int
    sender: str
    body: str
    created_at: datetime


class GlobalMessageOut(BaseModel):
    """A line in the everyone-chat; same shape as `MessageOut` minus the room."""

    id: int
    sender_id: int
    sender: str
    body: str
    created_at: datetime


# --- admin -------------------------------------------------------------------


class AdminUserOut(BaseModel):
    id: int
    username: str
    phone: str
    role: str
    created_at: datetime
    note_count: int
    message_count: int


class AdminUserUpdate(BaseModel):
    username: str

    @field_validator("username")
    @classmethod
    def clean_username(cls, value: str) -> str:
        value = re.sub(r"\s+", " ", value.strip())
        if not USERNAME_RE.fullmatch(value) or not 3 <= len(value) <= 60:
            raise ValueError(
                "username must be 3-60 letters with single spaces between words"
            )
        return value


# --- dashboard ---------------------------------------------------------------


class SubjectCount(BaseModel):
    subject_id: int
    name: str
    color: str | None
    count: int


class LabelCount(BaseModel):
    key: str
    label: str
    count: int


class DashboardNotes(BaseModel):
    total: int
    done: int
    without_subject: int
    by_subject: list[SubjectCount]
    by_kind: list[LabelCount]
    by_branch: list[LabelCount]
    by_semester: list[LabelCount]


class DashboardNote(BaseModel):
    id: int
    title: str
    author: str
    subject_id: int | None
    semester: int
    branch: str
    kind: str
    is_done: bool
    updated_at: datetime


class MessagePreview(BaseModel):
    sender: str
    body: str
    created_at: datetime


class DashboardGroup(BaseModel):
    id: int
    name: str
    member_count: int
    last_message: MessagePreview | None


class TrendPoint(BaseModel):
    date: str
    count: int


class DashboardOut(BaseModel):
    notes: DashboardNotes
    recent_notes: list[DashboardNote]
    groups: list[DashboardGroup]
    trend: list[TrendPoint]
