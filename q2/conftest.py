import os
import sys
from pathlib import Path
import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Ensure wardrobe directory is in sys.path
wardrobe_path = Path(__file__).resolve().parent.parent / "wardrobe"
if str(wardrobe_path) not in sys.path:
    sys.path.insert(0, str(wardrobe_path))

from backend.main import app
from backend.database import Base, get_db
from backend.models import User, Item, Upload, Session as SessionModel
from backend.auth import hash_password, create_session

# Dedicated Test Database for Q2 Test Suite
TEST_DB_FILE = Path(__file__).resolve().parent / "q2_test.db"
TEST_DB_URL = f"sqlite:///{TEST_DB_FILE}"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    if TEST_DB_FILE.exists():
        try:
            TEST_DB_FILE.unlink()
        except Exception:
            pass


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def user_a(db_session):
    user = User(
        email="usera@example.com",
        password_hash=hash_password("PasswordA123!"),
        display_name="User Alpha",
        is_admin=0,
        is_active=1
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def user_b(db_session):
    user = User(
        email="userb@example.com",
        password_hash=hash_password("PasswordB123!"),
        display_name="User Beta",
        is_admin=0,
        is_active=1
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_user(db_session):
    admin = User(
        email="admin_q2@example.com",
        password_hash=hash_password("AdminSecurePassword123!"),
        display_name="Q2 Administrator",
        is_admin=1,
        is_active=1
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def auth_client_a(db_session, user_a):
    token = create_session(db_session, user_a.id, "TestAgentAlpha")
    c = TestClient(app)
    c.cookies.set("session", token)
    return c


@pytest.fixture
def auth_client_b(db_session, user_b):
    token = create_session(db_session, user_b.id, "TestAgentBeta")
    c = TestClient(app)
    c.cookies.set("session", token)
    return c


@pytest.fixture
def auth_admin_client(db_session, admin_user):
    token = create_session(db_session, admin_user.id, "TestAgentAdmin")
    c = TestClient(app)
    c.cookies.set("session", token)
    return c
