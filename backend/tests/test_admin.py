from __future__ import annotations

import pytest

from app.config import settings
from app.database import SessionLocal
from app.models import User
from sqlalchemy import select

PDF = b"%PDF-1.4\n%%EOF\n"


def create_note(client, headers, **overrides):
    payload = {
        "title": "Shared note",
        "body": "",
        "semester": 2,
        "branch": "CSE",
        "kind": "notes",
        **overrides,
    }
    response = client.post("/api/notes", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def upload(client, headers, note_id):
    response = client.post(
        f"/api/notes/{note_id}/attachments",
        headers=headers,
        files={"file": ("notes.pdf", PDF, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def stored_files(note_id: int) -> set:
    folder = settings.upload_dir / str(note_id)
    return set(folder.iterdir()) if folder.exists() else set()


def get_user(username: str) -> User | None:
    db = SessionLocal()
    try:
        return db.scalar(select(User).where(User.username == username))
    finally:
        db.close()


def user_id(client, headers) -> int:
    return client.get("/api/auth/me", headers=headers).json()["id"]


def test_admin_lists_every_account(client, alice, bob, admin):
    users = client.get("/api/admin/users", headers=admin).json()

    by_name = {user["username"]: user for user in users}
    assert set(by_name) == {"alice", "bob", settings.admin_username}
    assert by_name["alice"]["phone"] == "9000000001"
    assert by_name["alice"]["role"] == "user"
    assert by_name[settings.admin_username]["role"] == "admin"
    assert by_name["alice"]["note_count"] == 0


def test_admin_sees_activity_counts(client, alice, admin):
    note = create_note(client, alice)
    upload(client, alice, note["id"])
    client.post("/api/chat", headers=alice, json={"body": "hello"})
    client.post("/api/chat", headers=alice, json={"body": "again"})

    users = client.get("/api/admin/users", headers=admin).json()
    alice_row = next(user for user in users if user["username"] == "alice")

    assert alice_row["note_count"] == 1
    assert alice_row["message_count"] == 2


def test_admin_renames_an_account(client, alice, admin):
    response = client.patch(
        f"/api/admin/users/{user_id(client, alice)}",
        headers=admin,
        json={"username": "Alice Renamed"},
    )

    assert response.status_code == 200
    assert response.json()["username"] == "Alice Renamed"
    assert get_user("Alice Renamed") is not None


def test_rename_rejects_symbols_and_digits(client, alice, admin):
    target = user_id(client, alice)
    for bad in ("Al1ce", "Al!ce", "a"):
        response = client.patch(
            f"/api/admin/users/{target}", headers=admin, json={"username": bad}
        )
        assert response.status_code == 422


def test_only_an_admin_can_rename(client, alice, bob, admin):
    assert (
        client.patch(
            f"/api/admin/users/{user_id(client, alice)}",
            headers=bob,
            json={"username": "Stolen"},
        ).status_code
        == 403
    )


def test_admin_deletes_an_account_with_its_files(client, alice, admin):
    note = create_note(client, alice)
    upload(client, alice, note["id"])
    assert len(stored_files(note["id"])) == 1
    target = user_id(client, alice)

    response = client.delete(f"/api/admin/users/{target}", headers=admin)

    assert response.status_code == 204
    assert get_user("alice") is None
    assert client.get("/api/notes", headers=alice).status_code == 401
    assert client.get(f"/api/notes/{note['id']}", headers=admin).status_code == 404
    assert stored_files(note["id"]) == set()


def test_admin_cannot_delete_their_own_account(client, admin):
    response = client.delete(
        f"/api/admin/users/{user_id(client, admin)}", headers=admin
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "You cannot delete your own account"


def test_deleting_an_account_twice_is_a_404(client, alice, admin):
    target = user_id(client, alice)
    client.delete(f"/api/admin/users/{target}", headers=admin)

    assert client.delete(f"/api/admin/users/{target}", headers=admin).status_code == 404


def test_admin_can_remove_any_note(client, alice, admin):
    note = create_note(client, alice)
    upload(client, alice, note["id"])

    response = client.delete(f"/api/admin/notes/{note['id']}", headers=admin)

    assert response.status_code == 204
    assert client.get(f"/api/notes/{note['id']}", headers=admin).status_code == 404
    assert stored_files(note["id"]) == set()


def test_admin_notes_listing_carries_the_author(client, alice, admin):
    create_note(client, alice, title="From alice")

    notes = client.get("/api/admin/notes", headers=admin).json()

    assert [(note["title"], note["author"]) for note in notes] == [
        ("From alice", "alice")
    ]


def test_admin_can_delete_global_chat_lines(client, alice, admin):
    sent = client.post("/api/chat", headers=alice, json={"body": "bad take"}).json()

    response = client.delete(f"/api/admin/chat/messages/{sent['id']}", headers=admin)

    assert response.status_code == 204
    assert client.get("/api/chat", headers=alice).json() == []


def test_admin_can_delete_group_chat_lines(client, alice, admin):
    group = client.post(
        "/api/groups", headers=alice, json={"name": "Study Crew"}
    ).json()
    sent = client.post(
        f"/api/groups/{group['id']}/messages",
        headers=alice,
        json={"body": "off topic"},
    ).json()

    response = client.delete(
        f"/api/admin/groups/{group['id']}/messages/{sent['id']}", headers=admin
    )

    assert response.status_code == 204
    history = client.get(
        f"/api/groups/{group['id']}/messages", headers=alice
    ).json()
    assert history == []


@pytest.mark.parametrize(
    "method, path, payload",
    [
        ("get", "/api/admin/users", None),
        ("get", "/api/admin/notes", None),
        ("delete", "/api/admin/notes/1", None),
        ("delete", "/api/admin/users/1", None),
        ("delete", "/api/admin/chat/messages/1", None),
        ("patch", "/api/admin/users/1", {"username": "New Name"}),
    ],
)
def test_admin_endpoints_reject_normal_users(client, alice, method, path, payload):
    kwargs = {"headers": alice}
    if payload is not None:
        kwargs["json"] = payload
    response = getattr(client, method)(path, **kwargs)

    assert response.status_code == 403

