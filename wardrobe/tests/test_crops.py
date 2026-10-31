import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import crops
from backend.auth import hash_password
from backend.config import settings
from backend.database import Base
from backend.main import app
from backend.database import get_db
from backend.models import User


engine = create_engine("sqlite:///./test_crops.db", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def crop_store(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_ROOT", str(tmp_path))
    Base.metadata.create_all(bind=engine)
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db

    db = TestingSessionLocal()
    users = [
        User(email="crop1@example.com", password_hash=hash_password("Password123!")),
        User(email="crop2@example.com", password_hash=hash_password("Password123!")),
    ]
    db.add_all(users)
    db.commit()
    for user in users:
        db.refresh(user)
    user_ids = [user.id for user in users]
    db.close()

    yield TestingSessionLocal(), user_ids

    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous
    Base.metadata.drop_all(bind=engine)


def test_put_then_get_returns_same_bytes(crop_store):
    db, (user_id, _) = crop_store
    try:
        payload = b"crop bytes"
        assert crops.put(db, user_id, "abc.png", payload) == len(payload)
        assert crops.get(db, user_id, "abc.png") == payload
    finally:
        db.close()


def test_put_same_name_twice_is_idempotent(crop_store):
    db, (user_id, _) = crop_store
    try:
        crops.put(db, user_id, "same.png", b"same image")
        crops.put(db, user_id, "same.png", b"same image")
        assert crops.names(db, user_id) == {"same.png"}
        assert crops.get(db, user_id, "same.png") == b"same image"
    finally:
        db.close()


def test_another_user_cannot_read_crop_by_name(crop_store):
    db, (owner_id, other_id) = crop_store
    try:
        crops.put(db, owner_id, "private.png", b"private bytes")
        assert crops.get(db, other_id, "private.png") is None
    finally:
        db.close()


def test_exists_is_false_for_unknown_crop(crop_store):
    db, (user_id, _) = crop_store
    try:
        assert crops.exists(db, user_id, "unknown.png") is False
    finally:
        db.close()


def test_traversal_name_cannot_escape_user_directory(crop_store, tmp_path):
    db, (user_id, _) = crop_store
    outside = tmp_path / "outside.png"
    try:
        assert crops.get(db, user_id, "../../outside.png") is None
        with pytest.raises(ValueError):
            crops.put(db, user_id, "../../outside.png", b"escape")
        assert not outside.exists()
    finally:
        db.close()


def test_names_only_lists_that_users_crops(crop_store):
    db, (first_id, second_id) = crop_store
    try:
        crops.put(db, first_id, "first.png", b"one")
        crops.put(db, second_id, "second.png", b"two")
        assert crops.names(db, first_id) == {"first.png"}
        assert crops.names(db, second_id) == {"second.png"}
    finally:
        db.close()
