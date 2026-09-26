import os

# Must happen before any `app.*` import so config picks up the test settings.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ENVIRONMENT", "test")
# Small enough that the "upload too large" test stays fast.
os.environ.setdefault("MAX_UPLOAD_BYTES", "4096")

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import Base, engine
from app.main import create_app

PASSWORD = "correct-horse"


@pytest.fixture(autouse=True)
def _database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _upload_dir(tmp_path, monkeypatch):
    """Keep every test's attachments in a folder of its own."""
    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


def _signup(client: TestClient, username: str, phone: str) -> dict:
    response = client.post(
        "/api/auth/register",
        json={"username": username, "phone": phone, "password": PASSWORD},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def alice(client) -> dict:
    """Authorization headers for a freshly registered user "alice"."""
    return _signup(client, "alice", "9000000001")


@pytest.fixture()
def bob(client) -> dict:
    """Authorization headers for a freshly registered user "bob"."""
    return _signup(client, "bob", "9000000002")


@pytest.fixture()
def carol(client) -> dict:
    """Authorization headers for a freshly registered user "carol"."""
    return _signup(client, "carol", "9000000003")


@pytest.fixture()
def admin(client) -> dict:
    """Authorization headers for the seeded moderation account."""
    from app.auth import seed_admin
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        seed_admin(db)
    finally:
        db.close()

    response = client.post(
        "/api/auth/login",
        json={"identifier": settings.admin_username, "password": settings.admin_password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
