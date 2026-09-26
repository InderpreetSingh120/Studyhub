"""Password hashing, JWT issuing/verification and the auth endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User
from .schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
    normalize_phone,
)

ALGORITHM = "HS256"
UNAUTHORIZED_HEADERS = {"WWW-Authenticate": "Bearer"}

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Return False instead of raising on malformed hashes or oversized input."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int, expires_minutes: int | None = None) -> str:
    minutes = settings.jwt_expire_minutes if expires_minutes is None else expires_minutes
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> int:
    """Return the user id, or raise `jwt.PyJWTError` for anything invalid."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    return int(payload["sub"])


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency: `Authorization: Bearer <token>` → the `User` row."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers=UNAUTHORIZED_HEADERS,
        )
    try:
        user_id = decode_access_token(credentials.credentials)
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers=UNAUTHORIZED_HEADERS,
        ) from exc
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers=UNAUTHORIZED_HEADERS,
        )
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency for the moderation endpoints."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def _find_user(identifier: str, db: Session) -> User | None:
    """Look a login attempt up by phone number, falling back to username.

    Usernames are display names and may repeat, so a name only resolves when
    exactly one account carries it; a clash asks for the phone number instead.
    """
    try:
        phone = normalize_phone(identifier)
    except ValueError:
        phone = None
    if phone is not None:
        return db.scalar(select(User).where(User.phone == phone))

    matches = list(
        db.scalars(
            select(User)
            .where(func.lower(User.username) == identifier.lower())
            .order_by(User.id)
            .limit(2)
        )
    )
    if len(matches) > 1:
        raise HTTPException(
            status_code=409,
            detail="Several accounts share this username; log in with your phone number",
        )
    return matches[0] if matches else None


def seed_admin(db: Session) -> User:
    """Create (or repair) the moderation account on every startup.

    Idempotent: development keeps a deterministic `admin` account so the
    moderator credentials survive a wiped database; `.env` can override them.
    """
    admin = db.scalar(select(User).where(User.role == "admin").order_by(User.id))
    if admin is None:
        admin = db.scalar(
            select(User)
            .where(User.username == settings.admin_username)
            .order_by(User.id)
        )

    if admin is None:
        phone = settings.admin_phone
        for digit in range(10):
            candidate = f"{settings.admin_phone[:9]}{digit}"
            if not db.scalar(select(User.id).where(User.phone == candidate)):
                phone = candidate
                break
        admin = User(
            username=settings.admin_username,
            phone=phone,
            hashed_password=hash_password(settings.admin_password),
            role="admin",
        )
        db.add(admin)
    else:
        admin.username = settings.admin_username
        admin.hashed_password = hash_password(settings.admin_password)
        admin.role = "admin"

    db.commit()
    db.refresh(admin)
    return admin


auth_router = APIRouter(prefix="/auth", tags=["auth"])

@auth_router.post(
    "/register", response_model=TokenResponse, status_code=201, summary="Create an account"
)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Usernames may repeat; the phone number is what has to be unique."""
    if db.scalar(select(User).where(User.phone == payload.phone)):
        raise HTTPException(
            status_code=409, detail="An account already exists for this phone number"
        )

    user = User(
        username=payload.username,
        phone=payload.phone,
        hashed_password=hash_password(payload.password),
        role="user",
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:  # lost a race with a concurrent registration
        db.rollback()
        raise HTTPException(
            status_code=409, detail="An account already exists for this phone number"
        ) from exc
    db.refresh(user)
    return TokenResponse(
        access_token=create_access_token(user.id), user=UserOut.model_validate(user)
    )


@auth_router.post("/login", response_model=TokenResponse, summary="Get an access token")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = _find_user(payload.identifier, db)
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=401, detail="Incorrect phone number or password"
        )
    return TokenResponse(
        access_token=create_access_token(user.id), user=UserOut.model_validate(user)
    )


@auth_router.get("/me", response_model=UserOut, summary="Current user")
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
