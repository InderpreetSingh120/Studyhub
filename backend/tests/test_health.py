from sqlalchemy import inspect

from app.database import engine
from app.main import create_app


def test_health_reports_ok(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["environment"] == "test"
    assert body["version"]


def test_unknown_route_returns_json_404(client):
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_database_tables_are_created(client):
    tables = inspect(engine).get_table_names()

    assert "users" in tables


def test_unhandled_error_returns_json_500():
    from fastapi.testclient import TestClient

    app = create_app()

    @app.get("/boom")
    def boom():
        raise RuntimeError("kaboom")

    response = TestClient(app, raise_server_exceptions=False).get("/boom")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
