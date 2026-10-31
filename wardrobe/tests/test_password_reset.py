import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.auth import create_session, hash_password, limiter
from backend.database import Base, get_db
from backend.main import app
from backend.models import Session as SessionModel, User

TEST_DB_URL = "sqlite:///./test_password_reset.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_database():
    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    limiter._storage.reset()
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    limiter._storage.reset()
    if previous_override is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous_override


@pytest.fixture
def client():
    return TestClient(app)


def make_user(is_admin=False, password="FamilyPassword123"):
    db = TestingSessionLocal()
    user = User(
        email=f"{'admin' if is_admin else 'member'}@example.com",
        password_hash=hash_password(password),
        display_name="Family member",
        is_admin=is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id
    db.close()
    return user_id


def login(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def user_email(user_id):
    db = TestingSessionLocal()
    email = db.query(User).filter(User.id == user_id).one().email
    db.close()
    return email


def test_non_admin_cannot_reset_password(client):
    member_id = make_user()
    db = TestingSessionLocal()
    member = db.query(User).filter(User.id == member_id).one()
    token = create_session(db, member.id)
    db.close()
    client.cookies.set("session", token)

    response = client.post(f"/api/admin/users/{member_id}/reset-password")

    assert response.status_code == 403


def test_admin_reset_replaces_password_and_revokes_sessions(client):
    admin_id = make_user(is_admin=True)
    member_id = make_user()
    db = TestingSessionLocal()
    admin = db.query(User).filter(User.id == admin_id).one()
    member = db.query(User).filter(User.id == member_id).one()
    admin_token = create_session(db, admin.id)
    old_member_token = create_session(db, member.id)
    db.close()
    client.cookies.set("session", admin_token)

    response = client.post(f"/api/admin/users/{member_id}/reset-password")
    assert response.status_code == 200
    new_password = response.json()["password"]

    assert login(client, user_email(member_id), "FamilyPassword123").status_code == 401
    assert login(client, user_email(member_id), new_password).status_code == 200
    old_session_client = TestClient(app)
    old_session_client.cookies.set("session", old_member_token)
    assert old_session_client.get("/api/auth/me").status_code == 401


def test_change_password_wrong_current_leaves_password_unchanged(client):
    user_id = make_user()
    db = TestingSessionLocal()
    user = db.query(User).filter(User.id == user_id).one()
    token = create_session(db, user.id)
    db.close()
    client.cookies.set("session", token)

    response = client.post("/api/auth/change-password", json={
        "current_password": "WrongPassword123",
        "new_password": "AnotherFamilyPass123",
    })

    assert response.status_code == 400
    assert login(client, user_email(user_id), "FamilyPassword123").status_code == 200


def test_change_password_keeps_request_session_working_and_removes_others(client):
    user_id = make_user()
    db = TestingSessionLocal()
    user = db.query(User).filter(User.id == user_id).one()
    request_token = create_session(db, user.id)
    other_token = create_session(db, user.id)
    db.close()
    client.cookies.set("session", request_token)

    response = client.post("/api/auth/change-password", json={
        "current_password": "FamilyPassword123",
        "new_password": "AnotherFamilyPass123",
    })

    assert response.status_code == 200
    assert client.get("/api/auth/me").status_code == 200
    client.cookies.set("session", other_token)
    assert client.get("/api/auth/me").status_code == 401
    assert login(client, user_email(user_id), "AnotherFamilyPass123").status_code == 200
