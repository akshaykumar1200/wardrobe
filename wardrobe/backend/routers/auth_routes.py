import hashlib
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, Request, Cookie
from sqlalchemy.orm import Session as DBSession

from backend.config import settings
from backend.database import get_db
from backend.models import User, Session as SessionModel, PasswordReset
from backend.schemas import SignupRequest, LoginRequest, UserOut, UserUpdate, ChangePasswordRequest, ForgotPasswordRequest, ResetPasswordRequest
from backend.auth import (
    hash_password, verify_password, create_session,
    current_user, session_token, limiter
)
from backend.mailer import send_reset_email

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/forgot-password")
@limiter.limit("5/hour")
def forgot_password(request: Request, payload: ForgotPasswordRequest,
                    background_tasks: BackgroundTasks, db: DBSession = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if user and user.is_active:
        db.query(PasswordReset).filter(
            PasswordReset.user_id == user.id,
            PasswordReset.used_at.is_(None),
        ).delete(synchronize_session=False)
        token = secrets.token_urlsafe(32)
        reset = PasswordReset(
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            user_id=user.id,
            expires_at=datetime.utcnow() + timedelta(minutes=settings.RESET_TOKEN_MINUTES),
        )
        db.add(reset)
        db.commit()
        reset_url = f"{settings.PUBLIC_ORIGIN.rstrip('/')}/reset?token={token}"
        background_tasks.add_task(send_reset_email, user.email, reset_url)
    return {"ok": True, "message": "If that address has an account, a reset link is on its way."}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: DBSession = Depends(get_db)):
    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    reset = db.query(PasswordReset).filter(PasswordReset.token_hash == token_hash).first()
    now = datetime.utcnow()
    if not reset or reset.used_at is not None or reset.expires_at <= now:
        raise HTTPException(400, "Reset link is invalid or expired")

    user = db.query(User).filter(User.id == reset.user_id).first()
    if user is None:
        raise HTTPException(400, "Reset link is invalid or expired")
    user.password_hash = hash_password(payload.new_password)
    reset.used_at = now
    db.query(SessionModel).filter(SessionModel.user_id == user.id).delete(synchronize_session=False)
    db.query(PasswordReset).filter(
        PasswordReset.user_id == user.id,
        PasswordReset.token_hash != token_hash,
        PasswordReset.used_at.is_(None),
    ).delete(synchronize_session=False)
    db.commit()
    return {"ok": True}


@router.post("/signup", response_model=UserOut)
@limiter.limit("3/minute")
def signup(request: Request, payload: SignupRequest, db: DBSession = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(400, "Email already registered")

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name or payload.email.split("@")[0]
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, payload: LoginRequest, response: Response,
          client: str | None = None, db: DBSession = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(user.password_hash, payload.password):
        raise HTTPException(401, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(401, "Account disabled")

    user_agent = request.headers.get("user-agent")
    token = create_session(db, user.id, user_agent)

    user.last_login = datetime.utcnow()
    db.commit()

    # Only a native client gets the raw token. Handing it to a browser would
    # put it within reach of any XSS, which is the whole point of httponly.
    if client == "mobile":
        return {"ok": True, "user": UserOut.model_validate(user), "token": token}

    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.SESSION_DAYS * 86400,
        path="/"
    )
    return {"ok": True, "user": UserOut.model_validate(user)}


@router.post("/logout")
def logout(response: Response, token: str | None = Depends(session_token), db: DBSession = Depends(get_db)):
    # Reads the Bearer header too, or a mobile session could never be revoked.
    if token:
        db.query(SessionModel).filter(SessionModel.token == token).delete()
        db.commit()
    response.delete_cookie(key="session", path="/")
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def get_me(user: User = Depends(current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(payload: UserUpdate, user: User = Depends(current_user), db: DBSession = Depends(get_db)):
    if payload.display_name is not None:
        user.display_name = payload.display_name
        db.commit()
        db.refresh(user)
    return user


@router.post("/change-password")
def change_password(payload: ChangePasswordRequest, user: User = Depends(current_user),
                    token: str | None = Depends(session_token), db: DBSession = Depends(get_db)):
    if not verify_password(user.password_hash, payload.current_password):
        raise HTTPException(400, "Current password is incorrect")
    if payload.new_password == payload.current_password:
        raise HTTPException(400, "New password must be different")

    user.password_hash = hash_password(payload.new_password)
    db.query(SessionModel).filter(
        SessionModel.user_id == user.id,
        SessionModel.token != token
    ).delete()
    db.commit()
    return {"ok": True}
