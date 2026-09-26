from __future__ import annotations


def create_group(client, headers, name="Study Crew", description=""):
    response = client.post(
        "/api/groups", headers=headers, json={"name": name, "description": description}
    )
    assert response.status_code == 201, response.text
    return response.json()


def join(client, headers, invite_code):
    return client.post(
        "/api/groups/join", headers=headers, json={"invite_code": invite_code}
    )


# --- creating and listing ---------------------------------------------------


def test_create_group_makes_you_the_owner(client, alice):
    group = create_group(client, alice, name="  Study Crew  ", description=" finals ")

    assert group["name"] == "Study Crew"
    assert group["description"] == "finals"
    assert group["my_role"] == "owner"
    assert group["member_count"] == 1
    assert len(group["invite_code"]) == 8
    assert group["invite_code"] == group["invite_code"].upper()


def test_create_group_rejects_a_blank_name(client, alice):
    assert client.post("/api/groups", headers=alice, json={"name": "  "}).status_code == 422


def test_list_groups_only_shows_your_own(client, alice, bob):
    first = create_group(client, alice, name="Alpha")
    create_group(client, alice, name="Beta")
    create_group(client, bob, name="Bob stuff")

    alice_groups = client.get("/api/groups", headers=alice).json()
    bob_groups = client.get("/api/groups", headers=bob).json()

    assert [g["name"] for g in alice_groups] == ["Alpha", "Beta"]
    assert first["id"] in {g["id"] for g in alice_groups}
    assert len({g["id"] for g in alice_groups}) == 2
    assert [g["name"] for g in bob_groups] == ["Bob stuff"]


# --- joining ----------------------------------------------------------------


def test_join_with_an_invite_code(client, alice, bob):
    group = create_group(client, alice)

    response = join(client, bob, group["invite_code"])

    assert response.status_code == 200, response.text
    assert response.json()["my_role"] == "member"
    assert response.json()["member_count"] == 2
    assert client.get("/api/groups", headers=bob).json()[0]["member_count"] == 2


def test_invite_code_is_accepted_in_lowercase(client, alice, bob):
    group = create_group(client, alice)

    response = join(client, bob, group["invite_code"].lower())

    assert response.status_code == 200


def test_join_with_an_unknown_code(client, bob):
    assert join(client, bob, "ZZZZZZZZ").status_code == 404


def test_join_rejects_a_malformed_code(client, bob):
    assert join(client, bob, "!!").status_code == 422


def test_cannot_join_the_same_group_twice(client, alice, bob):
    group = create_group(client, alice)
    join(client, bob, group["invite_code"])

    assert join(client, bob, group["invite_code"]).status_code == 409
    assert join(client, alice, group["invite_code"]).status_code == 409


def test_group_detail_is_for_members_only(client, alice, bob):
    group = create_group(client, alice)

    detail = client.get(f"/api/groups/{group['id']}", headers=bob)

    assert detail.status_code == 404
    assert client.get("/api/groups/999999", headers=alice).status_code == 404


# --- members ----------------------------------------------------------------


def test_members_list_shows_everyone_with_roles(client, alice, bob):
    group = create_group(client, alice)
    join(client, bob, group["invite_code"])

    members = client.get(
        f"/api/groups/{group['id']}/members", headers=bob
    ).json()

    assert [m["username"] for m in members] == ["alice", "bob"]
    assert [m["role"] for m in members] == ["owner", "member"]
    assert members[0]["joined_at"] <= members[1]["joined_at"]


def test_members_list_is_for_members_only(client, alice, bob):
    group = create_group(client, alice)

    assert (
        client.get(f"/api/groups/{group['id']}/members", headers=bob).status_code == 404
    )


# --- permissions ------------------------------------------------------------


def test_owner_can_rename_the_group(client, alice, bob):
    group = create_group(client, alice)
    join(client, bob, group["invite_code"])

    response = client.patch(
        f"/api/groups/{group['id']}", headers=alice, json={"name": "Renamed"}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Renamed"


def test_a_plain_member_cannot_change_or_delete_the_group(client, alice, bob):
    group = create_group(client, alice)
    join(client, bob, group["invite_code"])

    patch = client.patch(
        f"/api/groups/{group['id']}", headers=bob, json={"name": "Mine now"}
    )
    delete = client.delete(f"/api/groups/{group['id']}", headers=bob)

    assert patch.status_code == 403
    assert delete.status_code == 403
    assert (
        client.get(f"/api/groups/{group['id']}", headers=alice).json()["name"]
        == "Study Crew"
    )


def test_a_non_member_cannot_change_the_group(client, alice, bob):
    group = create_group(client, alice)

    assert (
        client.patch(
            f"/api/groups/{group['id']}", headers=bob, json={"name": "Nope"}
        ).status_code
        == 404
    )


def test_update_rejects_a_null_name(client, alice):
    group = create_group(client, alice)

    response = client.patch(
        f"/api/groups/{group['id']}", headers=alice, json={"name": None}
    )

    assert response.status_code == 422


def test_owner_can_delete_the_group(client, alice, bob):
    group = create_group(client, alice)
    join(client, bob, group["invite_code"])

    assert client.delete(f"/api/groups/{group['id']}", headers=alice).status_code == 204
    assert client.get(f"/api/groups/{group['id']}", headers=bob).status_code == 404
    assert client.get("/api/groups", headers=bob).json() == []


# --- leaving ----------------------------------------------------------------


def test_leaving_removes_you_from_the_group(client, alice, bob):
    group = create_group(client, alice)
    join(client, bob, group["invite_code"])

    assert client.post(f"/api/groups/{group['id']}/leave", headers=bob).status_code == 204
    assert client.get("/api/groups", headers=bob).json() == []
    assert (
        client.get(f"/api/groups/{group['id']}", headers=alice).json()["member_count"]
        == 1
    )
    assert (
        client.post(f"/api/groups/{group['id']}/leave", headers=bob).status_code == 404
    )


def test_an_owner_leaving_hands_over_the_group(client, alice, bob, carol):
    group = create_group(client, alice)
    join(client, bob, group["invite_code"])
    join(client, carol, group["invite_code"])

    assert client.post(f"/api/groups/{group['id']}/leave", headers=alice).status_code == 204

    detail = client.get(f"/api/groups/{group['id']}", headers=bob).json()
    assert detail["my_role"] == "owner"
    assert detail["member_count"] == 2
    assert detail["invite_code"] == group["invite_code"]
    assert client.get(f"/api/groups/{group['id']}", headers=alice).status_code == 404
    assert (
        client.delete(f"/api/groups/{group['id']}", headers=bob).status_code == 204
    )


def test_the_last_member_leaving_deletes_the_group(client, alice, bob):
    group = create_group(client, alice)
    code = group["invite_code"]

    assert client.post(f"/api/groups/{group['id']}/leave", headers=alice).status_code == 204

    assert client.get("/api/groups", headers=alice).json() == []
    assert join(client, bob, code).status_code == 404
