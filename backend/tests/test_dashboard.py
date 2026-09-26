from __future__ import annotations

from datetime import timedelta

from app.models import utcnow


def create_group(client, headers, name="Study Crew"):
    response = client.post("/api/groups", headers=headers, json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def create_subject(client, headers, name, color=None):
    response = client.post(
        "/api/subjects", headers=headers, json={"name": name, "color": color}
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_note(client, headers, title, subject_id=None, is_done=False, **overrides):
    payload = {
        "title": title,
        "subject_id": subject_id,
        "is_done": is_done,
        "semester": 3,
        "branch": "CSE",
        "kind": "notes",
        **overrides,
    }
    response = client.post("/api/notes", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def dashboard(client, headers):
    response = client.get("/api/dashboard", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_dashboard_requires_a_token(client):
    assert client.get("/api/dashboard").status_code == 401


def test_an_empty_dashboard(client, alice):
    data = dashboard(client, alice)

    assert data["notes"] == {
        "total": 0,
        "done": 0,
        "without_subject": 0,
        "by_subject": [],
        "by_kind": [],
        "by_branch": [],
        "by_semester": [
            {"key": str(index), "label": f"Semester {index}", "count": 0}
            for index in range(1, 9)
        ],
    }
    assert data["recent_notes"] == []
    assert data["groups"] == []
    assert len(data["trend"]) == 30
    assert data["trend"][-1]["count"] == 0


def test_trend_covers_the_last_30_days_oldest_first(client, alice):
    today = utcnow().date()

    assert [point["date"] for point in dashboard(client, alice)["trend"]] == [
        (today - timedelta(days=offset)).isoformat() for offset in range(29, -1, -1)
    ]


def test_notes_are_summed_per_subject(client, alice):
    algebra = create_subject(client, alice, "Algebra", color="#3b82f6")
    biology = create_subject(client, alice, "Biology")
    create_note(client, alice, "groups", algebra["id"], is_done=True)
    create_note(client, alice, "rings", algebra["id"])
    create_note(client, alice, "cells", biology["id"])
    create_note(client, alice, "loose thoughts")

    notes = dashboard(client, alice)["notes"]

    assert notes["total"] == 4
    assert notes["done"] == 1
    assert notes["without_subject"] == 1
    assert [(s["name"], s["count"]) for s in notes["by_subject"]] == [
        ("Algebra", 2),
        ("Biology", 1),
    ]
    assert notes["by_subject"][0]["subject_id"] == algebra["id"]
    assert notes["by_subject"][0]["color"] == "#3b82f6"
    assert notes["by_subject"][1]["color"] is None


def test_recent_notes_show_the_newest_five_first(client, alice):
    for index in range(7):
        create_note(client, alice, f"note {index}")

    recent = dashboard(client, alice)["recent_notes"]

    assert [note["title"] for note in recent] == [
        "note 6",
        "note 5",
        "note 4",
        "note 3",
        "note 2",
    ]
    assert recent[0]["subject_id"] is None
    assert recent[0]["is_done"] is False


def test_a_done_note_stays_in_recent_notes(client, alice):
    note = create_note(client, alice, "finish the report", is_done=True)

    recent = dashboard(client, alice)["recent_notes"]

    assert recent[0]["id"] == note["id"]
    assert recent[0]["is_done"] is True


def test_the_dashboard_counts_everyones_notes_but_only_my_groups(client, alice, bob):
    subject = create_subject(client, alice, "Algebra")
    create_note(client, alice, "groups", subject["id"])
    create_note(client, bob, "bob's cells", subject["id"])
    create_group(client, alice, name="Alice crew")

    data = dashboard(client, bob)

    assert data["notes"]["total"] == 2  # the gallery belongs to everyone
    assert data["groups"] == []  # groups stay personal
    assert data["recent_notes"][0]["author"] in {"alice", "bob"}


def test_notes_are_summed_per_kind_branch_and_semester(client, alice):
    create_note(client, alice, "lecture notes", kind="notes", branch="CSE", semester=1)
    create_note(client, alice, "lab manual", kind="practical", branch="CSE", semester=3)
    create_note(client, alice, "mst paper", kind="mst", branch="IT", semester=3)
    create_note(client, alice, "finals", kind="final", branch="IT", semester=5)

    notes = dashboard(client, alice)["notes"]

    assert [(k["key"], k["count"]) for k in notes["by_kind"]] == [
        ("final", 1),
        ("mst", 1),
        ("notes", 1),
        ("practical", 1),
    ]
    assert [(b["key"], b["count"]) for b in notes["by_branch"]] == [
        ("CSE", 2),
        ("IT", 2),
    ]
    assert [s["count"] for s in notes["by_semester"]] == [1, 0, 2, 0, 1, 0, 0, 0]


def test_groups_carry_the_member_count_and_last_message(client, alice, bob):
    quiet = create_group(client, alice, name="Quiet room")
    busy = create_group(client, alice, name="Busy room")
    assert (
        client.post(
            "/api/groups/join",
            headers=bob,
            json={"invite_code": busy["invite_code"]},
        ).status_code
        == 200
    )
    client.post(
        f"/api/groups/{busy['id']}/messages",
        headers=bob,
        json={"body": "who is up for a call?"},
    )

    groups = dashboard(client, alice)["groups"]

    assert [group["name"] for group in groups] == ["Busy room", "Quiet room"]
    assert groups[0]["member_count"] == 2
    assert groups[0]["last_message"]["sender"] == "bob"
    assert groups[0]["last_message"]["body"] == "who is up for a call?"
    assert groups[1]["member_count"] == 1
    assert groups[1]["last_message"] is None


def test_the_trend_counts_today(client, alice):
    create_note(client, alice, "written today")

    trend = dashboard(client, alice)["trend"]

    assert trend[-1]["count"] == 1
    assert sum(point["count"] for point in trend) == 1
