from __future__ import annotations

import pytest
from sqlalchemy import func, select
from starlette.websockets import WebSocketDisconnect

from app.database import SessionLocal
from app.models import Group, Message


def create_group(client, headers, name="Study Crew"):
    response = client.post("/api/groups", headers=headers, json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def join(client, headers, invite_code):
    response = client.post(
        "/api/groups/join", headers=headers, json={"invite_code": invite_code}
    )
    assert response.status_code == 200, response.text
    return response.json()


def send(client, headers, group_id, body):
    response = client.post(
        f"/api/groups/{group_id}/messages", headers=headers, json={"body": body}
    )
    assert response.status_code == 201, response.text
    return response.json()


def history(client, headers, group_id, **params):
    response = client.get(
        f"/api/groups/{group_id}/messages", headers=headers, params=params
    )
    assert response.status_code == 200, response.text
    return response.json()


def token(headers) -> str:
    return headers["Authorization"].split(" ", 1)[1]


# --- REST history ------------------------------------------------------------


def test_history_starts_empty(client, alice):
    group = create_group(client, alice)

    assert history(client, alice, group["id"]) == []


def test_messages_are_stored_with_their_sender(client, alice, bob):
    group = create_group(client, alice)
    join(client, bob, group["invite_code"])

    sent = send(client, alice, group["id"], "  hi bob  ")
    send(client, bob, group["id"], "hi alice")

    messages = history(client, alice, group["id"])

    assert sent["body"] == "hi bob"  # surrounding whitespace is trimmed
    assert [m["body"] for m in messages] == ["hi bob", "hi alice"]
    assert [m["sender"] for m in messages] == ["alice", "bob"]
    assert messages[0]["group_id"] == group["id"]
    assert messages[0]["created_at"]


def test_history_pages_backwards(client, alice):
    group = create_group(client, alice)
    for index in range(5):
        send(client, alice, group["id"], f"m{index}")

    newest_page = history(client, alice, group["id"], limit=2)
    older_page = history(
        client, alice, group["id"], before_id=newest_page[0]["id"], limit=2
    )
    oldest_page = history(
        client, alice, group["id"], before_id=older_page[0]["id"], limit=2
    )

    assert [m["body"] for m in newest_page] == ["m3", "m4"]
    assert [m["body"] for m in older_page] == ["m1", "m2"]
    assert [m["body"] for m in oldest_page] == ["m0"]
    # pages are always ordered oldest first, even though they walk backwards
    assert [m["id"] for m in older_page] == sorted(m["id"] for m in older_page)


def test_history_rejects_a_silly_page_size(client, alice):
    group = create_group(client, alice)

    assert (
        client.get(
            f"/api/groups/{group['id']}/messages", headers=alice, params={"limit": 0}
        ).status_code
        == 422
    )
    assert (
        client.get(
            f"/api/groups/{group['id']}/messages",
            headers=alice,
            params={"limit": 999},
        ).status_code
        == 422
    )


def test_history_is_for_members_only(client, alice, bob):
    group = create_group(client, alice)

    assert (
        client.get(f"/api/groups/{group['id']}/messages", headers=bob).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/groups/{group['id']}/messages",
            headers=bob,
            json={"body": "let me in"},
        ).status_code
        == 404
    )


def test_sending_requires_a_token(client, alice):
    group = create_group(client, alice)

    assert (
        client.post(
            f"/api/groups/{group['id']}/messages", json={"body": "anonymous"}
        ).status_code
        == 401
    )


def test_a_blank_message_is_rejected(client, alice):
    group = create_group(client, alice)

    assert (
        client.post(
            f"/api/groups/{group['id']}/messages",
            headers=alice,
            json={"body": "   "},
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/groups/{group['id']}/messages",
            headers=alice,
            json={"body": "x" * 4001},
        ).status_code
        == 422
    )


def test_deleting_a_group_deletes_its_messages(client, alice):
    group = create_group(client, alice)
    send(client, alice, group["id"], "goodbye")

    assert client.delete(f"/api/groups/{group['id']}", headers=alice).status_code == 204

    db = SessionLocal()
    try:
        assert db.scalar(select(func.count()).select_from(Message)) == 0
        assert db.scalar(select(func.count()).select_from(Group)) == 0
    finally:
        db.close()


# --- WebSocket ---------------------------------------------------------------


def test_a_member_can_open_a_socket(client, alice):
    group = create_group(client, alice)
    me = client.get("/api/auth/me", headers=alice).json()

    with client.websocket_connect(
        f"/api/ws/groups/{group['id']}?token={token(alice)}"
    ) as socket:
        assert socket.receive_json() == {
            "type": "connected",
            "group_id": group["id"],
            "user_id": me["id"],
        }


def test_a_sent_message_is_echoed_back_to_the_group(client, alice, bob):
    group = create_group(client, alice)
    join(client, bob, group["invite_code"])

    with client.websocket_connect(
        f"/api/ws/groups/{group['id']}?token={token(alice)}"
    ) as alice_socket, client.websocket_connect(
        f"/api/ws/groups/{group['id']}?token={token(bob)}"
    ) as bob_socket:
        assert alice_socket.receive_json()["type"] == "connected"
        assert bob_socket.receive_json()["type"] == "connected"

        alice_socket.send_json({"type": "message", "body": "anyone there?"})

        for socket in (alice_socket, bob_socket):
            envelope = socket.receive_json()
            assert envelope["type"] == "message"
            assert envelope["message"]["body"] == "anyone there?"
            assert envelope["message"]["sender"] == "alice"

    # the message was persisted, so history agrees with the socket
    assert [m["body"] for m in history(client, alice, group["id"])] == [
        "anyone there?"
    ]


def test_a_message_sent_over_rest_reaches_the_socket(client, alice, bob):
    group = create_group(client, alice)
    join(client, bob, group["invite_code"])

    with client.websocket_connect(
        f"/api/ws/groups/{group['id']}?token={token(alice)}"
    ) as alice_socket:
        assert alice_socket.receive_json()["type"] == "connected"
        send(client, bob, group["id"], "posted from REST")

        envelope = alice_socket.receive_json()
        assert envelope["message"]["sender"] == "bob"
        assert envelope["message"]["body"] == "posted from REST"


def test_one_group_does_not_hear_another(client, alice):
    first = create_group(client, alice, name="First")
    second = create_group(client, alice, name="Second")

    with client.websocket_connect(
        f"/api/ws/groups/{first['id']}?token={token(alice)}"
    ) as socket:
        assert socket.receive_json()["type"] == "connected"
        send(client, alice, second["id"], "wrong room")

        # A pong proves no message from the other group was queued ahead of it.
        socket.send_json({"type": "ping"})
        assert socket.receive_json() == {"type": "pong"}


def test_the_socket_needs_a_token(client, alice):
    group = create_group(client, alice)

    with client.websocket_connect(f"/api/ws/groups/{group['id']}") as socket:
        assert socket.receive_json() == {"type": "error", "detail": "unauthorized"}
        with pytest.raises(WebSocketDisconnect) as exc:
            socket.receive_json()
    assert exc.value.code == 4401


def test_the_socket_rejects_a_bad_token(client, alice):
    group = create_group(client, alice)

    with client.websocket_connect(
        f"/api/ws/groups/{group['id']}?token=not-a-jwt"
    ) as socket:
        assert socket.receive_json()["detail"] == "unauthorized"
        with pytest.raises(WebSocketDisconnect) as exc:
            socket.receive_json()
    assert exc.value.code == 4401


def test_the_socket_hides_groups_you_are_not_in(client, alice, bob):
    group = create_group(client, alice)

    with client.websocket_connect(
        f"/api/ws/groups/{group['id']}?token={token(bob)}"
    ) as socket:
        assert socket.receive_json() == {
            "type": "error",
            "detail": "Group not found",
        }
        with pytest.raises(WebSocketDisconnect) as exc:
            socket.receive_json()
    assert exc.value.code == 4404


def test_the_socket_answers_a_ping(client, alice):
    group = create_group(client, alice)

    with client.websocket_connect(
        f"/api/ws/groups/{group['id']}?token={token(alice)}"
    ) as socket:
        assert socket.receive_json()["type"] == "connected"
        socket.send_json({"type": "ping"})
        assert socket.receive_json() == {"type": "pong"}


@pytest.mark.parametrize(
    ("frame", "detail"),
    [
        ({"type": "message", "body": "   "}, "Value error, message must be 1-4000 characters"),
        ({"type": "dance"}, "unknown message type"),
        ({"type": "message", "body": "hi", "extra": True}, None),  # allowed
    ],
)
def test_the_socket_rejects_bad_frames(client, alice, frame, detail):
    group = create_group(client, alice)

    with client.websocket_connect(
        f"/api/ws/groups/{group['id']}?token={token(alice)}"
    ) as socket:
        assert socket.receive_json()["type"] == "connected"
        socket.send_json(frame)
        if detail is None:
            assert socket.receive_json()["type"] == "message"
            return
        response = socket.receive_json()
        assert response["type"] == "error"
        assert response["detail"] == detail

        # the connection survives a bad frame
        socket.send_json({"type": "ping"})
        assert socket.receive_json() == {"type": "pong"}


def test_the_socket_rejects_non_text_frames(client, alice):
    group = create_group(client, alice)

    with client.websocket_connect(
        f"/api/ws/groups/{group['id']}?token={token(alice)}"
    ) as socket:
        assert socket.receive_json()["type"] == "connected"
        socket.send_bytes(b"binary")

        assert socket.receive_json() == {
            "type": "error",
            "detail": "send text frames only",
        }
        socket.send_json({"type": "ping"})
        assert socket.receive_json() == {"type": "pong"}


def test_the_socket_rejects_invalid_json(client, alice):
    group = create_group(client, alice)

    with client.websocket_connect(
        f"/api/ws/groups/{group['id']}?token={token(alice)}"
    ) as socket:
        assert socket.receive_json()["type"] == "connected"
        socket.send_text("{not json")

        assert socket.receive_json() == {"type": "error", "detail": "invalid JSON"}


def test_the_group_keeps_working_after_a_socket_closes(client, alice, bob):
    group = create_group(client, alice)
    join(client, bob, group["invite_code"])

    with client.websocket_connect(
        f"/api/ws/groups/{group['id']}?token={token(alice)}"
    ) as alice_socket:
        assert alice_socket.receive_json()["type"] == "connected"
        send(client, alice, group["id"], "before i go")

    send(client, alice, group["id"], "sent with no socket open")

    with client.websocket_connect(
        f"/api/ws/groups/{group['id']}?token={token(bob)}"
    ) as bob_socket:
        assert bob_socket.receive_json()["type"] == "connected"
        send(client, bob, group["id"], "still connected")

        envelope = bob_socket.receive_json()
        assert envelope["message"]["body"] == "still connected"
        assert envelope["message"]["sender"] == "bob"


# --- global chat (the room everyone shares) ---------------------------------


def global_history(client, headers, **params):
    response = client.get("/api/chat", headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def global_send(client, headers, body):
    response = client.post("/api/chat", headers=headers, json={"body": body})
    assert response.status_code == 201, response.text
    return response.json()


def test_global_history_requires_a_token(client):
    assert client.get("/api/chat").status_code == 401
    assert client.post("/api/chat", json={"body": "hi"}).status_code == 401


def test_global_history_starts_empty(client, alice):
    assert global_history(client, alice) == []


def test_global_messages_are_shared_by_everyone(client, alice, bob):
    sent = global_send(client, alice, "  hello everyone  ")
    global_send(client, bob, "hi alice")

    seen_by_bob = global_history(client, bob)

    assert sent["body"] == "hello everyone"
    assert [m["body"] for m in seen_by_bob] == ["hello everyone", "hi alice"]
    assert [m["sender"] for m in seen_by_bob] == ["alice", "bob"]
    assert "group_id" not in seen_by_bob[0]
    assert seen_by_bob[0]["created_at"]


def test_global_history_pages_backwards(client, alice):
    for index in range(5):
        global_send(client, alice, f"g{index}")

    newest_page = global_history(client, alice, limit=2)
    older_page = global_history(
        client, alice, before_id=newest_page[0]["id"], limit=2
    )

    assert [m["body"] for m in newest_page] == ["g3", "g4"]
    assert [m["body"] for m in older_page] == ["g1", "g2"]
    assert [m["id"] for m in older_page] == sorted(m["id"] for m in older_page)


def test_a_global_message_reaches_every_socket(client, alice, bob):
    with client.websocket_connect(
        f"/api/ws/global?token={token(alice)}"
    ) as alice_socket, client.websocket_connect(
        f"/api/ws/global?token={token(bob)}"
    ) as bob_socket:
        assert alice_socket.receive_json()["type"] == "connected"
        assert bob_socket.receive_json()["type"] == "connected"

        alice_socket.send_json({"type": "message", "body": "anyone here?"})

        for socket in (alice_socket, bob_socket):
            envelope = socket.receive_json()
            assert envelope["type"] == "message"
            assert envelope["message"]["body"] == "anyone here?"
            assert envelope["message"]["sender"] == "alice"

    assert [m["body"] for m in global_history(client, alice)] == ["anyone here?"]


def test_a_global_message_sent_over_rest_reaches_the_socket(client, alice, bob):
    with client.websocket_connect(
        f"/api/ws/global?token={token(alice)}"
    ) as alice_socket:
        assert alice_socket.receive_json()["type"] == "connected"
        global_send(client, bob, "posted from REST")

        envelope = alice_socket.receive_json()
        assert envelope["message"]["sender"] == "bob"
        assert envelope["message"]["body"] == "posted from REST"


def test_group_and_global_rooms_do_not_mix(client, alice):
    group = create_group(client, alice)

    with client.websocket_connect(
        f"/api/ws/groups/{group['id']}?token={token(alice)}"
    ) as socket:
        assert socket.receive_json()["type"] == "connected"
        global_send(client, alice, "belongs to the global room")

        socket.send_json({"type": "ping"})
        assert socket.receive_json() == {"type": "pong"}


def test_the_global_socket_needs_a_token(client):
    with client.websocket_connect("/api/ws/global") as socket:
        assert socket.receive_json() == {"type": "error", "detail": "unauthorized"}

        with pytest.raises(WebSocketDisconnect) as exc:
            socket.receive_json()
        assert exc.value.code == 4401


def test_the_global_socket_rejects_a_bad_token(client):
    with client.websocket_connect("/api/ws/global?token=nope") as socket:
        assert socket.receive_json() == {"type": "error", "detail": "unauthorized"}

        with pytest.raises(WebSocketDisconnect) as exc:
            socket.receive_json()
        assert exc.value.code == 4401
