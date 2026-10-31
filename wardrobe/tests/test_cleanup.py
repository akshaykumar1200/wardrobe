"""Crop files are content-addressed and are written before the user accepts
them, so deletion and cleanup both have to be careful about who owns a file."""
import os
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database import Base, get_db
from backend.models import User, Item
from backend.auth import hash_password, create_session
from backend.config import settings
from backend.storage import sweep_orphan_crops, ORPHAN_CROP_AGE

TEST_DB_URL = "sqlite:///./test_cleanup.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def storage(tmp_path, monkeypatch):
    """Isolated STORAGE_ROOT so tests never touch the real wardrobe."""
    monkeypatch.setattr(settings, "STORAGE_ROOT", str(tmp_path))
    items = tmp_path / "users" / "1" / "items"
    items.mkdir(parents=True)
    return items


@pytest.fixture
def db(tmp_path):
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


def _user(db, email="a@example.com"):
    u = User(email=email, password_hash=hash_password("Password123!"), display_name="A")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_delete_keeps_file_another_item_still_uses(db, storage):
    """Two items can share one crop file, because the name is its sha256."""
    user = _user(db)
    shared = "deadbeef.png"
    (storage / shared).write_bytes(b"png")

    ids = []
    for name in ("Left", "Right"):
        item = Item(user_id=user.id, name=name, category="shoes",
                    stored_name=shared, color="#000000", bytes=3)
        db.add(item)
        db.commit()
        db.refresh(item)
        ids.append(item.id)

    token = create_session(db, user.id, "TestAgent")
    client = TestClient(app)
    client.cookies.set("session", token)

    assert client.delete(f"/api/items/{ids[0]}").status_code == 200
    assert (storage / shared).exists(), "deleting one item destroyed the other's image"

    assert client.delete(f"/api/items/{ids[1]}").status_code == 200
    assert not (storage / shared).exists(), "last reference gone but file kept"


def test_sweep_removes_only_stale_unreferenced_crops(db, storage):
    kept_ref = storage / "referenced.png"
    kept_new = storage / "mid-review.png"
    orphan = storage / "abandoned.png"
    for p in (kept_ref, kept_new, orphan):
        p.write_bytes(b"x" * 10)

    old = time.time() - ORPHAN_CROP_AGE - 60
    os.utime(kept_ref, (old, old))
    os.utime(orphan, (old, old))

    freed = sweep_orphan_crops(1, keep={kept_ref.name}, db=db)

    assert freed == 10
    assert kept_ref.exists(), "swept a file an item row points at"
    assert kept_new.exists(), "swept a crop still being reviewed"
    assert not orphan.exists(), "left an abandoned crop behind"
