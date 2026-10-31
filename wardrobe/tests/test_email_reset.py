import hashlib
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.auth import create_session, hash_password, limiter, verify_password
from backend.database import Base, get_db
from backend.main import app
from backend.models import PasswordReset, Session as SessionModel, User

TEST_DB_URL = "sqlite:///./test_email_reset.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_database(monkeypatch):
    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    limiter._storage.reset()
    Base.metadata.create_all(bind=engine)
    sent = []
    monkeypatch.setattr("backend.routers.auth_routes.send_reset_email", lambda address, link: sent.append((address, link)))
    yield sent
    Base.metadata.drop_all(bind=engine)
    limiter._storage.reset()
    if previous_override is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous_override


@pytest.fixture
def client():
    return TestClient(app)


def make_user(email="member@example.com", password="FamilyPassword123", is_active=1):
    db = TestingSessionLocal()
    user = User(email=email, password_hash=hash_password(password), display_name="Family member", is_active=is_active)
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id
    db.close()
    return user_id


def request_link(client, email):
    return client.post("/api/auth/forgot-password", json={"email": email})


def token_from_link(link):
    return parse_qs(urlparse(link).query)["token"][0]


def test_unknown_address_has_same_response_as_known_and_only_known_sends(client, setup_database):
    make_user()
    unknown = request_link(client, "unknown@example.com")
    known = request_link(client, "member@example.com")

    assert unknown.status_code == known.status_code == 200
    assert unknown.json() == known.json()
    assert len(setup_database) == 1
    assert setup_database[0][0] == "member@example.com"


def test_emailed_token_resets_password_and_stored_hash_is_not_raw(client, setup_database):
    user_id = make_user()
    assert request_link(client, "member@example.com").status_code == 200
    token = token_from_link(setup_database[0][1])

    db = TestingSessionLocal()
    row = db.query(PasswordReset).filter(PasswordReset.user_id == user_id).one()
    assert row.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert row.token_hash != token
    db.close()

    response = client.post("/api/auth/reset-password", json={"token": token, "new_password": "ChangedFamilyPass123"})
    assert response.status_code == 200
    db = TestingSessionLocal()
    user = db.query(User).filter(User.id == user_id).one()
    assert verify_password(user.password_hash, "ChangedFamilyPass123")
    db.close()


def test_reset_token_is_single_use(client, setup_database):
    make_user()
    request_link(client, "member@example.com")
    token = token_from_link(setup_database[0][1])
    payload = {"token": token, "new_password": "ChangedFamilyPass123"}

    assert client.post("/api/auth/reset-password", json=payload).status_code == 200
    second = client.post("/api/auth/reset-password", json=payload)
    assert second.status_code == 400
    assert second.json() == {"detail": "Reset link is invalid or expired"}


def test_expired_token_returns_400_and_leaves_password_unchanged(client, setup_database):
    user_id = make_user()
    request_link(client, "member@example.com")
    token = token_from_link(setup_database[0][1])
    db = TestingSessionLocal()
    row = db.query(PasswordReset).filter(PasswordReset.token_hash == hashlib.sha256(token.encode()).hexdigest()).one()
    row.expires_at = datetime.utcnow() - timedelta(minutes=1)
    db.commit()
    db.close()

    response = client.post("/api/auth/reset-password", json={"token": token, "new_password": "ChangedFamilyPass123"})
    assert response.status_code == 400
    db = TestingSessionLocal()
    user = db.query(User).filter(User.id == user_id).one()
    assert verify_password(user.password_hash, "FamilyPassword123")
    db.close()


def test_successful_reset_revokes_existing_session(client, setup_database):
    user_id = make_user()
    db = TestingSessionLocal()
    session = create_session(db, user_id)
    db.close()
    old_session_client = TestClient(app)
    old_session_client.cookies.set("session", session)
    assert old_session_client.get("/api/auth/me").status_code == 200

    request_link(client, "member@example.com")
    token = token_from_link(setup_database[0][1])
    assert client.post("/api/auth/reset-password", json={"token": token, "new_password": "ChangedFamilyPass123"}).status_code == 200
    assert old_session_client.get("/api/auth/me").status_code == 401
    db = TestingSessionLocal()
    assert db.query(SessionModel).filter(SessionModel.user_id == user_id).count() == 0
    db.close()


def test_second_reset_link_invalidates_first(client, setup_database):
    make_user()
    request_link(client, "member@example.com")
    first_token = token_from_link(setup_database[-1][1])
    request_link(client, "member@example.com")
    second_token = token_from_link(setup_database[-1][1])

    first = client.post("/api/auth/reset-password", json={"token": first_token, "new_password": "ChangedFamilyPass123"})
    second = client.post("/api/auth/reset-password", json={"token": second_token, "new_password": "ChangedFamilyPass123"})
    assert first.status_code == 400
    assert second.status_code == 200
