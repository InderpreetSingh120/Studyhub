from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from app.auth import create_access_token, seed_admin, verify_password
from app.config import settings
from app.database import SessionLocal
from app.models import User

VALID = {"username": "Alice Smith", "phone": "9876543210", "password": "correct-horse"}


def register(client, **overrides):
    return client.post("/api/auth/register", json={**VALID, **overrides})


def login(client, identifier, password=VALID["password"]):
    return client.post(
        "/api/auth/login", json={"identifier": identifier, "password": password}
    )


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def get_user(username: str) -> User | None:
    db = SessionLocal()
    try:
        return db.scalar(select(User).where(User.username == username))
    finally:
        db.close()


# --- registration -----------------------------------------------------------


def test_register_returns_token_and_user(client):
    response = register(client)

    assert response.status_code == 201
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["user"]["id"]
    assert body["user"]["username"] == "Alice Smith"
    assert body["user"]["phone"] == "9876543210"
    assert body["user"]["role"] == "user"
    assert body["user"]["created_at"]


def test_register_response_never_contains_the_password(client):
    body = register(client).json()

    assert "password" not in body["user"]
    assert "hashed_password" not in body["user"]
    assert "password" not in body


def test_register_collapses_spaces_in_the_username(client):
    body = register(client, username="   Bob   Kumar  ").json()

    assert body["user"]["username"] == "Bob Kumar"


@pytest.mark.parametrize(
    "phone",
    ["9876543210", "+919876543210", "+91 98765 43210", "09876543210", "98765-43210"],
)
def test_register_normalizes_every_phone_format(client, phone):
    body = register(client, phone=phone).json()

    assert body["user"]["phone"] == "9876543210"


def test_two_accounts_may_share_a_username_but_not_a_phone(client):
    assert register(client).status_code == 201
    assert register(client, phone="9111111111").status_code == 201

    response = register(client, phone="9222222222")
    assert response.status_code == 201


@pytest.mark.parametrize(
    "overrides, status",
    [
        ({"phone": "9876543210"}, 409),  # same phone, different name
        ({"password": "short"}, 422),
        ({"username": "Alice1"}, 422),  # digits are not allowed
        ({"username": "Al!ce"}, 422),  # symbols are not allowed
        ({"username": "ab"}, 422),  # too short
        ({"username": "   "}, 422),
        ({"phone": "12345"}, 422),
        ({"phone": "987654321012345"}, 422),
        ({"phone": "not-a-number"}, 422),
    ],
)
def test_register_rejects_bad_input(client, overrides, status):
    assert register(client).status_code == 201  # baseline that later requests collide with

    response = register(client, **overrides)

    assert response.status_code == status


def test_conflict_is_distinct_from_validation_error(client):
    assert register(client).status_code == 201

    response = register(client)

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "An account already exists for this phone number"
    )


# --- password storage -------------------------------------------------------


def test_password_is_hashed_with_bcrypt(client):
    register(client)

    user = get_user("Alice Smith")

    assert user is not None
    assert user.hashed_password != VALID["password"]
    assert user.hashed_password.startswith("$2")
    assert verify_password(VALID["password"], user.hashed_password)
    assert not verify_password("wrong-password", user.hashed_password)


# --- login ------------------------------------------------------------------


def test_login_with_phone(client):
    register(client)

    response = login(client, "9876543210")

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert response.json()["user"]["username"] == "Alice Smith"


def test_login_accepts_a_formatted_phone_number(client):
    register(client)

    assert login(client, "+91 98765 43210").status_code == 200


def test_login_with_a_unique_username(client):
    register(client)

    response = login(client, "alice smith")

    assert response.status_code == 200
    assert response.json()["user"]["username"] == "Alice Smith"


def test_login_by_username_is_rejected_when_the_name_is_shared(client):
    register(client)
    register(client, phone="9111111111")

    response = login(client, "Alice Smith")

    assert response.status_code == 409
    assert "phone number" in response.json()["detail"]


@pytest.mark.parametrize(
    "identifier, password",
    [
        ("9876543210", "wrong-password"),
        ("9999999999", "correct-horse"),
        ("Alice Smith", "wrong-password"),
    ],
)
def test_login_rejects_bad_credentials(client, identifier, password):
    register(client)

    response = login(client, identifier, password)

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect phone number or password"


# --- authenticated requests -------------------------------------------------


def test_me_returns_current_user(client):
    token = register(client).json()["access_token"]

    response = client.get("/api/auth/me", headers=bearer(token))

    assert response.status_code == 200
    assert response.json()["username"] == "Alice Smith"
    assert response.json()["phone"] == "9876543210"


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer nope"}, {"Authorization": "Basic dXNlcjpwdw=="}])
def test_me_requires_a_valid_bearer_token(client, headers):
    register(client)

    response = client.get("/api/auth/me", headers=headers)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_me_rejects_expired_token(client):
    token = register(client).json()["access_token"]
    user_id = get_user("Alice Smith").id
    expired = create_access_token(user_id, expires_minutes=-1)

    assert expired != token
    assert client.get("/api/auth/me", headers=bearer(expired)).status_code == 401


def test_me_rejects_token_signed_with_another_secret(client):
    import jwt

    from app.auth import ALGORITHM

    register(client)
    forged = jwt.encode(
        {"sub": "1"}, "a-totally-different-and-long-enough-secret", algorithm=ALGORITHM
    )

    assert client.get("/api/auth/me", headers=bearer(forged)).status_code == 401


def test_me_rejects_token_for_a_deleted_user(client):
    token = register(client).json()["access_token"]

    db = SessionLocal()
    try:
        db.execute(delete(User))
        db.commit()
    finally:
        db.close()

    assert client.get("/api/auth/me", headers=bearer(token)).status_code == 401


# --- seeded admin -----------------------------------------------------------


def test_admin_account_is_seeded_and_can_log_in(client):
    db = SessionLocal()
    try:
        admin = seed_admin(db)
        assert admin.username == settings.admin_username
        assert admin.role == "admin"
        again = seed_admin(db)  # idempotent: no second account
        assert again.id == admin.id
    finally:
        db.close()

    response = login(client, settings.admin_username, settings.admin_password)

    assert response.status_code == 200
    assert response.json()["user"]["role"] == "admin"


def test_admin_endpoints_are_for_admins_only(client, alice):
    assert client.get("/api/admin/users", headers=alice).status_code == 403
    assert client.get("/api/admin/users").status_code == 401


# --- secret handling --------------------------------------------------------


def test_production_refuses_to_start_without_a_secret(monkeypatch):
    from app.config import _jwt_secret

    monkeypatch.setenv("JWT_SECRET", "")
    with pytest.raises(RuntimeError):
        _jwt_secret("production")

    monkeypatch.setenv("JWT_SECRET", "replace-me")
    with pytest.raises(RuntimeError):
        _jwt_secret("production")


def test_development_uses_a_random_per_process_secret(monkeypatch):
    from app.config import _jwt_secret

    monkeypatch.delenv("JWT_SECRET", raising=False)

    first, second = _jwt_secret("development"), _jwt_secret("development")

    assert first != second
    assert len(first) >= 32
