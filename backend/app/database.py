"""Database engine, session factory and declarative base.

`DATABASE_URL` is the only thing that changes when moving from SQLite
(development) to PostgreSQL (deployment).
"""

from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import settings

_is_sqlite = settings.database_url.startswith("sqlite")
connect_args = {"check_same_thread": False} if _is_sqlite else {}
# A single in-memory database is shared by every thread when tests use
# `sqlite:///:memory:`; without StaticPool each connection would be empty.
pool = (
    StaticPool
    if settings.database_url in ("sqlite://", "sqlite:///:memory:")
    else None
)

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    poolclass=pool,
    pool_pre_ping=True,
)

if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        """SQLite ignores FOREIGN KEY clauses unless this pragma is set."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency that yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
