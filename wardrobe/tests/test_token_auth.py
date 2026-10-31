"""A native mobile client cannot rely on the httponly session cookie, so the
same token has to work in an Authorization: Bearer header."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database import Base, get_db
from backend.models import User, Session as SessionModel
from backend.auth import hash_password, create_session

engine = create_engine("sqlite:///./test_token.db", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

PASSWORD = "Password123!"


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    # test_security.py installs its own override at import time; restore it or
    # that module falls through to the real wardrobe.db.
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    session = TestingSessionLocal()
    yield session
    session.close()
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous
    Base.metadata.drop_all(bind=engine)


def _user(db, email="phone@example.com"):
    u = User(email=email, password_hash=hash_password(PASSWORD), display_name="P")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_mobile_login_returns_token_and_sets_no_cookie(db):
    _user(db)
    c = TestClient(app)
    res = c.post("/api/auth/login?client=mobile",
                 json={"email": "phone@example.com", "password": PASSWORD})

    assert res.status_code == 200, res.text
    assert res.json()["token"], "mobile login gave no token"
    assert "session" not in res.cookies, "handed a cookie to a native client"


def test_bearer_token_authenticates_with_no_cookie(db):
    _user(db)
    c = TestClient(app)
    token = c.post("/api/auth/login?client=mobile",
                   json={"email": "phone@example.com", "password": PASSWORD}).json()["token"]
    c.cookies.clear()

    res = c.get("/api/items", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, f"Bearer token rejected: {res.text}"


def test_web_login_is_unchanged(db):
    """No client param: cookie as before, and the token stays out of the body
    so an XSS cannot read it."""
    _user(db)
    c = TestClient(app)
    res = c.post("/api/auth/login", json={"email": "phone@example.com", "password": PASSWORD})

    assert res.status_code == 200, res.text
    assert "session" in res.cookies
    assert "token" not in res.json()


def test_garbage_bearer_token_is_rejected(db):
    c = TestClient(app)
    assert c.get("/api/items", headers={"Authorization": "Bearer not-a-real-token"}).status_code == 401
    assert c.get("/api/items", headers={"Authorization": "Basic abc"}).status_code == 401


def test_expired_session_rejected_via_bearer(db):
    """Expiry must be enforced on the header path too, not just the cookie."""
    user = _user(db)
    token = create_session(db, user.id, "TestAgent")
    row = db.query(SessionModel).filter(SessionModel.token == token).first()
    row.expires_at = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    db.commit()

    c = TestClient(app)
    res = c.get("/api/items", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401, "expired token accepted over the header path"


def test_logout_revokes_a_bearer_session(db):
    """Without this, a phone could never sign out."""
    user = _user(db)
    token = create_session(db, user.id, "TestAgent")
    c = TestClient(app)
    auth = {"Authorization": f"Bearer {token}"}

    assert c.post("/api/auth/logout", headers=auth).status_code == 200
    assert c.get("/api/items", headers=auth).status_code == 401


def test_display_name_is_validated(db):
    """PATCH /api/auth/me took any string, including empty or enormous."""
    user = _user(db, "profile@example.com")
    token = create_session(db, user.id, "TestAgent")
    c = TestClient(app)
    auth = {"Authorization": f"Bearer {token}"}

    assert c.patch("/api/auth/me", json={"display_name": "   "}, headers=auth).status_code == 422
    assert c.patch("/api/auth/me", json={"display_name": "x" * 61}, headers=auth).status_code == 422

    ok = c.patch("/api/auth/me", json={"display_name": "  Aksh  "}, headers=auth)
    assert ok.status_code == 200, ok.text
    assert ok.json()["display_name"] == "Aksh", "name was not trimmed"
