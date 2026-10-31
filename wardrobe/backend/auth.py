import secrets
from datetime import datetime, timedelta, timezone
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, Header, HTTPException, Cookie, Request
from sqlalchemy.orm import Session as DBSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.config import settings
from backend.database import get_db
from backend.models import User, Session

ph = PasswordHasher()


def get_real_ip(request: Request) -> str:
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


limiter = Limiter(key_func=get_real_ip)


def hash_password(pw: str) -> str:
    return ph.hash(pw)


def verify_password(hash_: str, pw: str) -> bool:
    try:
        ph.verify(hash_, pw)
        return True
    except VerifyMismatchError:
        return False


def create_session(db: DBSession, user_id: int, user_agent: str | None = None) -> str:
    token = secrets.token_urlsafe(48)
    expires = datetime.now(timezone.utc) + timedelta(days=settings.SESSION_DAYS)
    new_session = Session(
        token=token,
        user_id=user_id,
        expires_at=expires.isoformat(),
        user_agent=(user_agent or "")[:255]
    )
    db.add(new_session)
    db.commit()
    return token


def session_token(
    session: str | None = Cookie(None),
    authorization: str | None = Header(None),
) -> str | None:
    """The session token, from the cookie or an `Authorization: Bearer` header.

    A browser sends the httponly cookie for us; a native mobile client cannot,
    so it passes the same token in a header. The cookie wins when both are
    present, so the web path is unchanged.
    """
    if session:
        return session
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer" and value.strip():
            return value.strip()
    return None


def current_user(
    token: str | None = Depends(session_token),
    db: DBSession = Depends(get_db),
) -> User:
    if not token:
        raise HTTPException(401, "Not authenticated")
    row = db.query(Session).filter(Session.token == token).first()
    if not row:
        raise HTTPException(401, "Invalid session")
    try:
        expires_dt = datetime.fromisoformat(row.expires_at)
    except Exception:
        db.delete(row)
        db.commit()
        raise HTTPException(401, "Invalid session format")

    if expires_dt < datetime.now(timezone.utc):
        db.delete(row)
        db.commit()
        raise HTTPException(401, "Session expired")

    user = db.query(User).filter(User.id == row.user_id, User.is_active == 1).first()
    if not user:
        raise HTTPException(401, "User not found or inactive")
    return user


def current_admin(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, "Admin access required")
    return user
