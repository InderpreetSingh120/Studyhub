from __future__ import annotations

import pytest

from app.config import settings

PDF = b"%PDF-1.4\n%%EOF\n"


def stored_files(note_id: int) -> set:
    """Files currently stored for a note (the upload folder is per test)."""
    folder = settings.upload_dir / str(note_id)
    return set(folder.iterdir()) if folder.exists() else set()


def create_subject(client, headers, name="Algebra", color=None):
    response = client.post(
        "/api/subjects", headers=headers, json={"name": name, "color": color}
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_note(client, headers, **overrides):
    payload = {
        "title": "Untitled",
        "body": "",
        "semester": 3,
        "branch": "CSE",
        "kind": "notes",
        **overrides,
    }
    response = client.post("/api/notes", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def upload(client, headers, note_id, data=PDF, name="notes.pdf", content_type="application/pdf"):
    return client.post(
        f"/api/notes/{note_id}/attachments",
        headers=headers,
        files={"file": (name, data, content_type)},
    )


# --- subjects ---------------------------------------------------------------


def test_create_list_and_read_subject(client, alice):
    created = create_subject(client, alice, name="  Linear Algebra  ", color="#3B82F6")

    assert created["name"] == "Linear Algebra"
    assert created["color"] == "#3b82f6"
    assert [s["name"] for s in client.get("/api/subjects", headers=alice).json()] == [
        "Linear Algebra"
    ]


@pytest.mark.parametrize("name", ["", "   "])
def test_subject_name_cannot_be_blank(client, alice, name):
    assert (
        client.post("/api/subjects", headers=alice, json={"name": name}).status_code
        == 422
    )


@pytest.mark.parametrize("color", ["blue", "#fff", "#12345g", "red"])
def test_subject_rejects_bad_colors(client, alice, color):
    assert (
        client.post(
            "/api/subjects", headers=alice, json={"name": "Art", "color": color}
        ).status_code
        == 422
    )


def test_subject_duplicate_names_conflict_case_insensitively(client, alice):
    create_subject(client, alice, name="Algebra")

    response = client.post(
        "/api/subjects", headers=alice, json={"name": "  algebra "}
    )

    assert response.status_code == 409


def test_update_subject(client, alice):
    subject = create_subject(client, alice)

    response = client.patch(
        f"/api/subjects/{subject['id']}",
        headers=alice,
        json={"name": "Calculus", "color": "#ef4444"},
    )

    assert response.status_code == 200
    assert response.json() == {**subject, "name": "Calculus", "color": "#ef4444"}


def test_update_subject_rejects_null_name(client, alice):
    subject = create_subject(client, alice)

    response = client.patch(
        f"/api/subjects/{subject['id']}", headers=alice, json={"name": None}
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "name"]


def test_update_subject_rejects_a_conflicting_name(client, alice):
    create_subject(client, alice, name="Algebra")
    calculus = create_subject(client, alice, name="Calculus")

    response = client.patch(
        f"/api/subjects/{calculus['id']}", headers=alice, json={"name": "algebra"}
    )

    assert response.status_code == 409


def test_deleting_a_subject_keeps_its_notes(client, alice):
    subject = create_subject(client, alice)
    note = create_note(client, alice, subject_id=subject["id"])

    assert (
        client.delete(f"/api/subjects/{subject['id']}", headers=alice).status_code
        == 204
    )
    assert client.get("/api/subjects", headers=alice).json() == []
    assert client.get(f"/api/notes/{note['id']}", headers=alice).json()[
        "subject_id"
    ] is None


def test_subjects_are_shared_but_only_the_creator_edits_them(client, alice, bob, admin):
    subject = create_subject(client, alice)

    assert [s["name"] for s in client.get("/api/subjects", headers=bob).json()] == [
        "Algebra"
    ]
    assert (
        client.patch(
            f"/api/subjects/{subject['id']}", headers=bob, json={"name": "Stolen"}
        ).status_code
        == 403
    )
    assert (
        client.delete(f"/api/subjects/{subject['id']}", headers=bob).status_code == 403
    )
    # the admin moderates the shared list
    assert (
        client.patch(
            f"/api/subjects/{subject['id']}", headers=admin, json={"name": "Fixed"}
        ).status_code
        == 200
    )


# --- notes ------------------------------------------------------------------


def test_create_note_with_defaults(client, alice):
    note = create_note(client, alice, title="  Chapter 3  ")

    assert note["title"] == "Chapter 3"
    assert note["body"] == ""
    assert note["is_done"] is False
    assert note["subject_id"] is None
    assert note["semester"] == 3
    assert note["branch"] == "CSE"
    assert note["kind"] == "notes"
    assert note["kind_label"] == "Notes"
    assert note["author"] == "alice"
    assert note["attachment_count"] == 0
    assert note["created_at"]
    assert note["updated_at"]


def test_create_note_rejects_blank_title(client, alice):
    assert (
        client.post(
            "/api/notes",
            headers=alice,
            json={"title": "   ", "semester": 1, "branch": "CSE"},
        ).status_code
        == 422
    )


@pytest.mark.parametrize("semester", [0, 9, -1])
def test_create_note_rejects_a_bad_semester(client, alice, semester):
    response = client.post(
        "/api/notes",
        headers=alice,
        json={"title": "Odd", "semester": semester, "branch": "CSE"},
    )

    assert response.status_code == 422


@pytest.mark.parametrize("kind", ["essay", "EXAM", ""])
def test_create_note_rejects_an_unknown_kind(client, alice, kind):
    response = client.post(
        "/api/notes",
        headers=alice,
        json={"title": "Odd", "semester": 1, "branch": "CSE", "kind": kind},
    )

    assert response.status_code == 422


def test_create_note_rejects_a_blank_branch(client, alice):
    response = client.post(
        "/api/notes",
        headers=alice,
        json={"title": "Odd", "semester": 1, "branch": "   "},
    )

    assert response.status_code == 422


def test_a_subject_can_be_used_by_anyone(client, alice, bob):
    subject = create_subject(client, bob)

    note = create_note(client, alice, title="Shared topic", subject_id=subject["id"])

    assert note["subject_id"] == subject["id"]


def test_notes_are_public_but_only_the_owner_writes_them(client, alice, bob):
    note = create_note(client, alice, title="Shared plans")

    read = client.get(f"/api/notes/{note['id']}", headers=bob)
    assert read.status_code == 200
    assert read.json()["author"] == "alice"

    assert (
        client.patch(
            f"/api/notes/{note['id']}", headers=bob, json={"title": "Hacked"}
        ).status_code
        == 403
    )
    assert client.delete(f"/api/notes/{note['id']}", headers=bob).status_code == 403
    assert [n["id"] for n in client.get("/api/notes", headers=bob).json()] == [
        note["id"]
    ]


def test_list_notes_returns_newest_first(client, alice):
    first = create_note(client, alice, title="First")
    second = create_note(client, alice, title="Second")

    ids = [n["id"] for n in client.get("/api/notes", headers=alice).json()]

    assert ids == [second["id"], first["id"]]


def test_search_matches_title_and_body(client, alice):
    create_note(client, alice, title="Fourier transforms", body="basics")
    create_note(client, alice, title="Organic chemistry", body="the fourier series")
    create_note(client, alice, title="History", body="nothing relevant")

    titles = [
        n["title"]
        for n in client.get("/api/notes", headers=alice, params={"q": "FOURIER"}).json()
    ]

    assert titles == ["Organic chemistry", "Fourier transforms"]


def test_search_ignores_like_wildcards_in_the_query(client, alice):
    create_note(client, alice, title="Score 100%")
    create_note(client, alice, title="Score 99 percent")

    matches = client.get("/api/notes", headers=alice, params={"q": "100%"}).json()

    assert [n["title"] for n in matches] == ["Score 100%"]


def test_search_finds_notes_from_everyone(client, alice, bob):
    create_note(client, bob, title="Bob secret formula")

    matches = client.get("/api/notes", headers=alice, params={"q": "secret"}).json()

    assert [(n["title"], n["author"]) for n in matches] == [
        ("Bob secret formula", "bob")
    ]


def test_filter_by_subject_and_completion(client, alice):
    subject = create_subject(client, alice)
    done_note = create_note(client, alice, title="Done", is_done=True)
    open_note = create_note(
        client, alice, title="Open", subject_id=subject["id"], is_done=False
    )

    by_subject = client.get(
        "/api/notes", headers=alice, params={"subject_id": subject["id"]}
    ).json()
    open_notes = client.get("/api/notes", headers=alice, params={"done": False}).json()
    done_notes = client.get("/api/notes", headers=alice, params={"done": True}).json()

    assert [n["id"] for n in by_subject] == [open_note["id"]]
    assert [n["id"] for n in open_notes] == [open_note["id"]]
    assert [n["id"] for n in done_notes] == [done_note["id"]]


def test_filter_by_semester_branch_and_kind(client, alice):
    create_note(client, alice, title="Sem 1", semester=1, branch="CSE", kind="notes")
    practical = create_note(
        client, alice, title="Lab", semester=3, branch="CSE", kind="practical"
    )
    create_note(client, alice, title="MST", semester=3, branch="IT", kind="mst")

    by_semester = client.get(
        "/api/notes", headers=alice, params={"semester": 3}
    ).json()
    by_branch = client.get("/api/notes", headers=alice, params={"branch": "cse"}).json()
    by_kind = client.get(
        "/api/notes", headers=alice, params={"kind": "practical"}
    ).json()
    combined = client.get(
        "/api/notes",
        headers=alice,
        params={"semester": 3, "branch": "CSE", "kind": "practical"},
    ).json()

    assert {n["title"] for n in by_semester} == {"Lab", "MST"}
    assert {n["title"] for n in by_branch} == {"Sem 1", "Lab"}
    assert [n["id"] for n in by_kind] == [practical["id"]]
    assert [n["id"] for n in combined] == [practical["id"]]


def test_mine_filter_keeps_my_uploads_separate(client, alice, bob):
    create_note(client, alice, title="Mine")
    create_note(client, bob, title="Theirs")

    mine = client.get("/api/notes", headers=alice, params={"mine": True}).json()
    everyone = client.get("/api/notes", headers=alice).json()

    assert [n["title"] for n in mine] == ["Mine"]
    assert {n["title"] for n in everyone} == {"Mine", "Theirs"}


def test_list_notes_rejects_an_unknown_kind(client, alice):
    response = client.get("/api/notes", headers=alice, params={"kind": "essay"})

    assert response.status_code == 400
    assert "kind must be one of" in response.json()["detail"]


def test_notes_count_their_attachments(client, alice, bob):
    note = create_note(client, alice)
    upload(client, alice, note["id"])
    upload(client, alice, note["id"], data=b"\x89PNG\r\n\x1a\n", name="x.png", content_type="image/png")

    gallery = client.get("/api/notes", headers=bob).json()

    assert gallery[0]["attachment_count"] == 2


def test_pagination(client, alice):
    ids = {create_note(client, alice, title=f"Note {i}")["id"] for i in range(5)}
    page = client.get("/api/notes", headers=alice, params={"limit": 2, "offset": 2}).json()

    assert len(page) == 2
    assert {n["id"] for n in page} <= ids
    assert (
        client.get("/api/notes", headers=alice, params={"limit": 0}).status_code == 422
    )


def test_update_note_changes_only_the_given_fields(client, alice):
    note = create_note(client, alice, title="Original", body="keep me")

    response = client.patch(
        f"/api/notes/{note['id']}", headers=alice, json={"is_done": True}
    )

    updated = response.json()
    assert response.status_code == 200
    assert updated["is_done"] is True
    assert updated["title"] == "Original"
    assert updated["body"] == "keep me"
    assert updated["subject_id"] is None
    assert updated["updated_at"] >= note["updated_at"]


def test_update_note_moves_between_subjects_and_back(client, alice):
    subject = create_subject(client, alice)
    note = create_note(client, alice)

    moved = client.patch(
        f"/api/notes/{note['id']}", headers=alice, json={"subject_id": subject["id"]}
    ).json()
    cleared = client.patch(
        f"/api/notes/{note['id']}", headers=alice, json={"subject_id": None}
    ).json()

    assert moved["subject_id"] == subject["id"]
    assert cleared["subject_id"] is None


@pytest.mark.parametrize(
    "patch",
    [
        {"title": None},
        {"body": None},
        {"is_done": None},
        {"title": "   "},
    ],
)
def test_update_note_rejects_invalid_values(client, alice, patch):
    note = create_note(client, alice)

    assert (
        client.patch(f"/api/notes/{note['id']}", headers=alice, json=patch).status_code
        == 422
    )


def test_delete_note(client, alice):
    note = create_note(client, alice)

    assert client.delete(f"/api/notes/{note['id']}", headers=alice).status_code == 204
    assert client.get(f"/api/notes/{note['id']}", headers=alice).status_code == 404
    assert client.get("/api/notes", headers=alice).json() == []


# --- attachments ------------------------------------------------------------


def test_upload_and_download_a_pdf(client, alice):
    note = create_note(client, alice)

    created = upload(client, alice, note["id"])

    assert created.status_code == 201, created.text
    body = created.json()
    assert body["filename"] == "notes.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["size_bytes"] == len(PDF)
    # The upload response is written before the background summary job runs.
    assert body["summary_status"] == "pending"
    assert body["summary"] is None
    listed = client.get(f"/api/notes/{note['id']}/attachments", headers=alice).json()
    # No API key in tests, so the job marks the file `skipped`.
    assert listed[0]["summary_status"] == "skipped"
    assert len(stored_files(note["id"])) == 1

    download = client.get(
        f"/api/notes/{note['id']}/attachments/{body['id']}", headers=alice
    )
    assert download.status_code == 200
    assert download.content == PDF
    assert download.headers["content-type"] == "application/pdf"
    assert "notes.pdf" in download.headers["content-disposition"]


def test_upload_strips_the_client_path_from_the_filename(client, alice):
    note = create_note(client, alice)

    created = upload(client, alice, note["id"], name="..\\..\\evil<script>.pdf")

    assert created.status_code == 201
    assert created.json()["filename"] == "evil_script_.pdf"


def test_list_attachments(client, alice):
    note = create_note(client, alice)
    upload(client, alice, note["id"])
    upload(client, alice, note["id"], data=b"\x89PNG\r\n\x1a\n", name="x.png", content_type="image/png")

    listed = client.get(f"/api/notes/{note['id']}/attachments", headers=alice)

    assert listed.status_code == 200
    assert [a["filename"] for a in listed.json()] == ["notes.pdf", "x.png"]
    assert "storage_key" not in listed.json()[0]


def test_delete_attachment_removes_the_stored_file(client, alice):
    note = create_note(client, alice)
    attachment = upload(client, alice, note["id"]).json()
    assert len(stored_files(note["id"])) == 1

    response = client.delete(
        f"/api/notes/{note['id']}/attachments/{attachment['id']}", headers=alice
    )

    assert response.status_code == 204
    assert client.get(f"/api/notes/{note['id']}/attachments", headers=alice).json() == []
    assert stored_files(note["id"]) == set()


def test_delete_note_removes_its_attachments(client, alice):
    note = create_note(client, alice)
    upload(client, alice, note["id"])
    assert len(stored_files(note["id"])) == 1

    assert client.delete(f"/api/notes/{note['id']}", headers=alice).status_code == 204
    assert stored_files(note["id"]) == set()


def test_upload_rejects_unsupported_file_types(client, alice):
    note = create_note(client, alice)

    response = upload(
        client, alice, note["id"], data=b"hello", name="notes.txt", content_type="text/plain"
    )

    assert response.status_code == 415
    assert stored_files(note["id"]) == set()


def test_upload_accepts_octet_stream_when_the_extension_is_known(client, alice):
    note = create_note(client, alice)

    created = upload(client, alice, note["id"], content_type="application/octet-stream")

    assert created.status_code == 201, created.text
    assert created.json()["content_type"] == "application/pdf"


def test_upload_rejects_octet_stream_with_an_unknown_extension(client, alice):
    note = create_note(client, alice)

    response = upload(
        client, alice, note["id"], data=b"PK", name="archive.zip", content_type="application/octet-stream"
    )

    assert response.status_code == 415
    assert stored_files(note["id"]) == set()


def test_upload_rejects_files_over_the_size_limit(client, alice):
    note = create_note(client, alice)

    response = upload(client, alice, note["id"], data=b"x" * 5000)

    assert response.status_code == 413
    assert stored_files(note["id"]) == set()


def test_attachments_are_public_to_read_and_owner_only_to_change(client, alice, bob):
    note = create_note(client, alice)
    attachment = upload(client, alice, note["id"]).json()

    assert upload(client, bob, note["id"]).status_code == 403
    listed = client.get(f"/api/notes/{note['id']}/attachments", headers=bob)
    assert listed.status_code == 200
    downloaded = client.get(
        f"/api/notes/{note['id']}/attachments/{attachment['id']}", headers=bob
    )
    assert downloaded.status_code == 200
    assert downloaded.content == PDF
    assert (
        client.delete(
            f"/api/notes/{note['id']}/attachments/{attachment['id']}", headers=bob
        ).status_code
        == 403
    )


def test_storage_keys_cannot_escape_the_upload_folder():
    from app.services import local_path

    assert local_path("12/deadbeef.pdf").is_relative_to(
        settings.upload_dir.resolve()
    )

    for key in ("../../etc/passwd", "/etc/passwd", "..\\..\\windows"):
        with pytest.raises(ValueError):
            local_path(key)
