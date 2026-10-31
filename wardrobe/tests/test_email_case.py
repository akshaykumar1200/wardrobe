import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.auth import limiter
from backend.database import Base, get_db
from backend.main import app
from backend.models import PasswordReset, User

TEST_DB_URL = "sqlite:///./test_email_case.db"
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
    monkeypatch.setattr("backend.routers.auth_routes.send_reset_email", lambda address, link: None)
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


def signup(client, email):
    return client.post("/api/auth/signup", json={
        "email": email,
        "password": "FamilyPassword123",
    })


def login(client, email):
    return client.post("/api/auth/login", json={
        "email": email,
        "password": "FamilyPassword123",
    })


def test_login_accepts_lowercase_address_after_mixed_case_signup(client):
    assert signup(client, "Akshaypsg30@gmail.com").status_code == 200

    assert login(client, "akshaypsg30@gmail.com").status_code == 200


def test_login_accepts_uppercase_address_after_mixed_case_signup(client):
    assert signup(client, "Akshaypsg30@gmail.com").status_code == 200

    assert login(client, "AKSHAYPSG30@GMAIL.COM").status_code == 200


def test_signup_rejects_duplicate_address_with_different_case(client):
    assert signup(client, "Akshaypsg30@gmail.com").status_code == 200

    duplicate = signup(client, "AKSHAYPSG30@GMAIL.COM")

    assert duplicate.status_code == 400
    assert duplicate.json() == {"detail": "Email already registered"}
    db = TestingSessionLocal()
    assert db.query(User).count() == 1
    db.close()


def test_forgot_password_finds_address_with_different_case(client):
    assert signup(client, "Akshaypsg30@gmail.com").status_code == 200

    response = client.post("/api/auth/forgot-password", json={"email": "AKSHAYPSG30@GMAIL.COM"})

    assert response.status_code == 200
    db = TestingSessionLocal()
    user = db.query(User).one()
    assert db.query(PasswordReset).filter(PasswordReset.user_id == user.id).count() == 1
    db.close()


def test_signup_and_login_strip_surrounding_email_spaces(client):
    assert signup(client, "  Akshaypsg30@gmail.com  ").status_code == 200

    assert login(client, "  AKSHAYPSG30@GMAIL.COM  ").status_code == 200

    db = TestingSessionLocal()
    assert db.query(User).one().email == "akshaypsg30@gmail.com"
    db.close()
