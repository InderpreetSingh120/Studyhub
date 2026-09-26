"""Environment-driven configuration.

Values come from process environment first, then from a `.env` file at the
repository root. No extra dependency is used for this; the reader below is
intentionally small.
"""

from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent

logger = logging.getLogger("studyhub")


def _load_env_file(path: Path) -> None:
    """Parse KEY=VALUE lines into os.environ without overriding existing values."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_env_file(Path(os.environ.get("ENV_FILE", PROJECT_ROOT / ".env")))


def _resolve_sqlite_url(url: str) -> str:
    """Anchor relative SQLite paths to the backend folder, not the cwd."""
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return url
    path = url[len(prefix) :]
    if not path or path == ":memory:":
        return url
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = BACKEND_DIR / resolved
    return prefix + resolved.resolve().as_posix()


def _jwt_secret(environment: str) -> str:
    """Read the signing secret from the environment, never from source code.

    Production refuses to start without a real secret. Development falls back
    to a random per-process secret so the server still runs with zero config.
    """
    secret = os.environ.get("JWT_SECRET", "").strip()
    if secret and secret != "replace-me":
        return secret
    if environment == "production":
        raise RuntimeError(
            "JWT_SECRET must be set when ENVIRONMENT=production "
            "(generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\")"
        )
    logger.warning(
        "JWT_SECRET is not set; using a random development secret. "
        "Issued tokens will not survive a restart."
    )
    return secrets.token_urlsafe(48)


def _admin_password(environment: str) -> str:
    """Password for the seeded moderation account.

    Development falls back to a documented default so a fresh clone still has a
    usable moderator. Production refuses to start with a placeholder or that
    default, mirroring the `JWT_SECRET` rule above.
    """
    password = os.environ.get("ADMIN_PASSWORD", "").strip() or "headachefromu"
    if environment == "production" and password in ("change-me", "headachefromu"):
        raise RuntimeError(
            "ADMIN_PASSWORD must be set to a real value when ENVIRONMENT=production "
            "(it seeds the moderation account)"
        )
    return password


def _storage_backend(value: str) -> str:
    """Validate STORAGE_BACKEND and require credentials for the S3 option."""
    if value not in ("local", "s3"):
        raise RuntimeError(f"STORAGE_BACKEND must be 'local' or 's3', got {value!r}")
    if value == "s3":
        missing = [
            name
            for name, key in (
                ("STORAGE_BUCKET", "STORAGE_BUCKET"),
                ("STORAGE_ACCESS_KEY_ID", "STORAGE_ACCESS_KEY_ID"),
                ("STORAGE_SECRET_ACCESS_KEY", "STORAGE_SECRET_ACCESS_KEY"),
            )
            if not os.environ.get(key)
        ]
        if missing:
            raise RuntimeError(
                "STORAGE_BACKEND=s3 requires " + ", ".join(missing)
            )
    return value


@dataclass
class Settings:
    project_name: str
    app_version: str
    environment: str
    api_prefix: str
    database_url: str
    cors_origins: tuple[str, ...]
    jwt_secret: str
    jwt_expire_minutes: int
    storage_backend: str
    storage_bucket: str
    storage_access_key_id: str
    storage_secret_access_key: str
    storage_endpoint: str
    storage_region: str
    storage_public_url: str
    upload_dir: Path
    max_upload_bytes: int
    openrouter_api_key: str
    summary_model: str
    summary_max_chars: int
    summary_max_tokens: int
    admin_username: str
    admin_password: str
    admin_phone: str

    @classmethod
    def from_env(cls) -> Settings:
        environment = os.environ.get("ENVIRONMENT", "development")
        origins = tuple(
            origin.strip()
            for origin in os.environ.get(
                "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
            ).split(",")
            if origin.strip()
        )
        default_db = f"sqlite:///{(BACKEND_DIR / 'study.db').as_posix()}"
        storage_backend = os.environ.get("STORAGE_BACKEND", "local").strip().lower()
        return cls(
            project_name=os.environ.get("PROJECT_NAME", "StudyHub API"),
            app_version=os.environ.get("APP_VERSION", "0.1.0"),
            environment=environment,
            api_prefix=os.environ.get("API_PREFIX", "/api"),
            database_url=_resolve_sqlite_url(
                os.environ.get("DATABASE_URL", default_db)
            ),
            cors_origins=origins,
            jwt_secret=_jwt_secret(environment),
            jwt_expire_minutes=int(os.environ.get("JWT_EXPIRE_MINUTES", "10080")),
            storage_backend=_storage_backend(storage_backend),
            storage_bucket=os.environ.get("STORAGE_BUCKET", ""),
            storage_access_key_id=os.environ.get("STORAGE_ACCESS_KEY_ID", ""),
            storage_secret_access_key=os.environ.get("STORAGE_SECRET_ACCESS_KEY", ""),
            storage_endpoint=os.environ.get("STORAGE_ENDPOINT", ""),
            storage_region=os.environ.get("STORAGE_REGION", "auto"),
            storage_public_url=os.environ.get("STORAGE_PUBLIC_URL", "").rstrip("/"),
            upload_dir=Path(
                os.environ.get("UPLOAD_DIR", str(BACKEND_DIR / "uploads"))
            ),
            max_upload_bytes=int(os.environ.get("MAX_UPLOAD_BYTES", str(20 * 1024 * 1024))),
            openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", "").strip(),
            summary_model=os.environ.get(
                "SUMMARY_MODEL", "meta-llama/llama-3.3-70b-instruct:free"
            ).strip(),
            summary_max_chars=int(os.environ.get("SUMMARY_MAX_CHARS", "16000")),
            summary_max_tokens=int(os.environ.get("SUMMARY_MAX_TOKENS", "400")),
            admin_username=os.environ.get("ADMIN_USERNAME", "admin").strip(),
            # Dev seed credentials for the moderation account; override in `.env`.
            admin_password=_admin_password(environment),
            admin_phone=os.environ.get("ADMIN_PHONE", "0000000000").strip(),
        )


settings = Settings.from_env()

if not settings.openrouter_api_key:
    logger.warning(
        "OPENROUTER_API_KEY is not set; PDF uploads are stored without an AI summary."
    )
