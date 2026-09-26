"""Chat: REST history plus a live WebSocket for each room.

Two kinds of room share one protocol and one connection registry:

- a group (`/api/groups/{id}/messages`, `/api/ws/groups/{id}`) - invite-only,
  membership rules from `groups.py`, non-members see `404`;
- the global room (`/api/chat`, `/api/ws/global`) - everyone who is logged in.

History is available over plain REST so either client can render a timeline
without a socket; the socket adds fan-out.
"""

from __future__ import annotations

import json
from typing import Protocol

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import decode_access_token, get_current_user
from .database import get_db
from .groups import _member_access
from .models import GlobalMessage, Message, User
from .schemas import GlobalMessageOut, MessageIn, MessageOut

messages_router = APIRouter(prefix="/groups", tags=["chat"])
global_chat_router = APIRouter(prefix="/chat", tags=["chat"])
chat_router = APIRouter(prefix="/ws", tags=["chat"])

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200

# The registry keys rooms by an int; group ids start at 1, so 0 is free for
# the one global room.
GLOBAL_CHANNEL = 0

# Close codes reserved for this protocol (4000-4999 is the private range).
UNAUTHORIZED_CODE = 4401
NOT_FOUND_CODE = 4404


class ConnectionRegistry:
    """In-process `channel → sockets` map used to fan a message out.

    One backend process serves every client, which is why a plain dict is
    enough; a shared broker is the documented upgrade path if the app is ever
    run as more than one replica.
    """

    def __init__(self) -> None:
        self._sockets: dict[int, set[WebSocket]] = {}

    def add(self, channel: int, websocket: WebSocket) -> None:
        self._sockets.setdefault(channel, set()).add(websocket)

    def remove(self, channel: int, websocket: WebSocket) -> None:
        sockets = self._sockets.get(channel)
        if sockets is None:
            return
        sockets.discard(websocket)
        if not sockets:
            self._sockets.pop(channel, None)

    def sockets(self, channel: int) -> list[WebSocket]:
        return list(self._sockets.get(channel, ()))

    def clear(self) -> None:
        self._sockets.clear()


class Channel(Protocol):
    """A chat room: a registry key plus how to persist one message."""

    key: int

    def post(self, db: Session, user: User, body: str) -> dict: ...


class GroupChannel:
    """Messages of a single group, fanned out to that group's sockets."""

    def __init__(self, group_id: int) -> None:
        self.key = group_id

    def post(self, db: Session, user: User, body: str) -> dict:
        message = Message(group_id=self.key, sender_id=user.id, body=body)
        db.add(message)
        db.commit()
        db.refresh(message)
        out = MessageOut(
            id=message.id,
            group_id=message.group_id,
            sender_id=message.sender_id,
            sender=user.username,
            body=message.body,
            created_at=message.created_at,
        )
        return {"type": "message", "message": out.model_dump(mode="json")}


class GlobalChannel:
    """The one room every logged-in user shares."""

    key = GLOBAL_CHANNEL

    def post(self, db: Session, user: User, body: str) -> dict:
        message = GlobalMessage(sender_id=user.id, body=body)
        db.add(message)
        db.commit()
        db.refresh(message)
        out = GlobalMessageOut(
            id=message.id,
            sender_id=message.sender_id,
            sender=user.username,
            body=message.body,
            created_at=message.created_at,
        )
        return {"type": "message", "message": out.model_dump(mode="json")}


def _message_out(message: Message, sender: str) -> MessageOut:
    return MessageOut(
        id=message.id,
        group_id=message.group_id,
        sender_id=message.sender_id,
        sender=sender,
        body=message.body,
        created_at=message.created_at,
    )


def _group_rows(
    db: Session, group_id: int, before_id: int | None, limit: int
) -> list[MessageOut]:
    """Newest `limit` messages strictly older than `before_id`, oldest first."""
    stmt = (
        select(Message, User.username)
        .join(User, User.id == Message.sender_id)
        .where(Message.group_id == group_id)
    )
    if before_id is not None:
        stmt = stmt.where(Message.id < before_id)
    # `id` doubles as the sort key: it is monotonically increasing per insert.
    rows = db.execute(stmt.order_by(Message.id.desc()).limit(limit)).all()
    return [_message_out(message, username) for message, username in reversed(rows)]


def _global_rows(
    db: Session, before_id: int | None, limit: int
) -> list[GlobalMessageOut]:
    stmt = (
        select(GlobalMessage, User.username)
        .join(User, User.id == GlobalMessage.sender_id)
    )
    if before_id is not None:
        stmt = stmt.where(GlobalMessage.id < before_id)
    rows = db.execute(stmt.order_by(GlobalMessage.id.desc()).limit(limit)).all()
    return [
        GlobalMessageOut(
            id=message.id,
            sender_id=message.sender_id,
            sender=username,
            body=message.body,
            created_at=message.created_at,
        )
        for message, username in reversed(rows)
    ]


async def _broadcast(registry: ConnectionRegistry, channel: int, envelope: dict) -> None:
    """Send one envelope to every socket in a room, dropping dead ones."""
    for websocket in registry.sockets(channel):
        try:
            await websocket.send_json(envelope)
        except Exception:
            registry.remove(channel, websocket)


async def _authenticate(websocket: WebSocket, token: str | None, db: Session) -> User | None:
    if not token:
        return None
    try:
        return db.get(User, decode_access_token(token))
    except (jwt.PyJWTError, ValueError, KeyError):
        return None


# --- group chat REST ---------------------------------------------------------


@messages_router.get(
    "/{group_id}/messages",
    response_model=list[MessageOut],
    summary="Read chat history",
)
def list_messages(
    group_id: int,
    before_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MessageOut]:
    """Page backwards through history: pass the oldest id you hold as
    `before_id` to fetch the page before it."""
    _member_access(group_id, current_user, db)
    return _group_rows(db, group_id, before_id, limit)


@messages_router.post(
    "/{group_id}/messages",
    response_model=MessageOut,
    status_code=201,
    summary="Send a message",
)
async def post_message(
    group_id: int,
    payload: MessageIn,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageOut:
    """Persist a message and fan it out to whoever is connected right now."""
    _member_access(group_id, current_user, db)
    envelope = GroupChannel(group_id).post(db, current_user, payload.body)
    registry = request.app.state.chat_connections
    await _broadcast(registry, group_id, envelope)
    return MessageOut(**envelope["message"])


# --- global chat REST --------------------------------------------------------


@global_chat_router.get(
    "",
    response_model=list[GlobalMessageOut],
    summary="Read the everyone-chat",
)
def list_global_messages(
    before_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[GlobalMessageOut]:
    return _global_rows(db, before_id, limit)


@global_chat_router.post(
    "",
    response_model=GlobalMessageOut,
    status_code=201,
    summary="Send a message to everyone",
)
async def post_global_message(
    payload: MessageIn,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GlobalMessageOut:
    envelope = GlobalChannel().post(db, current_user, payload.body)
    registry = request.app.state.chat_connections
    await _broadcast(registry, GLOBAL_CHANNEL, envelope)
    return GlobalMessageOut(**envelope["message"])


# --- sockets -----------------------------------------------------------------


async def _group_socket(
    websocket: WebSocket,
    group_id: int,
    token: str | None,
    db: Session,
    registry: ConnectionRegistry,
) -> None:
    user = await _authenticate(websocket, token, db)
    if user is None:
        await websocket.send_json({"type": "error", "detail": "unauthorized"})
        await websocket.close(code=UNAUTHORIZED_CODE)
        return

    try:
        _member_access(group_id, user, db)
    except HTTPException as exc:
        await websocket.send_json({"type": "error", "detail": exc.detail})
        await websocket.close(code=NOT_FOUND_CODE)
        return

    registry.add(group_id, websocket)
    await websocket.send_json(
        {"type": "connected", "group_id": group_id, "user_id": user.id}
    )
    try:
        await _socket_loop(websocket, GroupChannel(group_id), user, db, registry)
    finally:
        registry.remove(group_id, websocket)


@chat_router.websocket("/groups/{group_id}")
async def group_socket(
    websocket: WebSocket,
    group_id: int,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> None:
    """Live chat for one group.

    The browser and the Android client cannot send an `Authorization` header
    during the handshake, so the token travels as `?token=`. Protocol in both
    directions is JSON with a `type` field:

    - client → server: `{"type": "message", "body": "..."}`, `{"type": "ping"}`
    - server → client: `connected`, `message`, `pong`, `error`
    """
    await websocket.accept()
    await _group_socket(websocket, group_id, token, db, websocket.app.state.chat_connections)


@chat_router.websocket("/global")
async def global_socket(
    websocket: WebSocket,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> None:
    """Live chat for the room everyone shares; same frame protocol."""
    await websocket.accept()
    user = await _authenticate(websocket, token, db)
    if user is None:
        await websocket.send_json({"type": "error", "detail": "unauthorized"})
        await websocket.close(code=UNAUTHORIZED_CODE)
        return

    registry = websocket.app.state.chat_connections
    registry.add(GLOBAL_CHANNEL, websocket)
    await websocket.send_json(
        {"type": "connected", "group_id": GLOBAL_CHANNEL, "user_id": user.id}
    )
    try:
        await _socket_loop(websocket, GlobalChannel(), user, db, registry)
    finally:
        registry.remove(GLOBAL_CHANNEL, websocket)


async def _socket_loop(
    websocket: WebSocket,
    channel: Channel,
    user: User,
    db: Session,
    registry: ConnectionRegistry,
) -> None:
    """Read frames until the peer goes away, answering each one."""
    while True:
        frame = await websocket.receive()
        if frame["type"] == "websocket.disconnect":
            return
        raw = frame.get("text")
        if raw is None:
            await websocket.send_json(
                {"type": "error", "detail": "send text frames only"}
            )
            continue

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            await websocket.send_json({"type": "error", "detail": "invalid JSON"})
            continue
        if not isinstance(data, dict):
            await websocket.send_json(
                {"type": "error", "detail": "expected a JSON object"}
            )
            continue

        kind = data.get("type")
        if kind == "ping":
            await websocket.send_json({"type": "pong"})
            continue
        if kind != "message":
            await websocket.send_json(
                {"type": "error", "detail": "unknown message type"}
            )
            continue

        try:
            payload = MessageIn.model_validate(data)
        except ValidationError as exc:
            await websocket.send_json(
                {"type": "error", "detail": exc.errors()[0]["msg"]}
            )
            continue

        envelope = channel.post(db, user, payload.body)
        await _broadcast(registry, channel.key, envelope)
