"""Creating items: manual garments have no photo, and the client does not get
to tell the server how big a file is."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database import Base, get_db
from backend.models import User, Item
from backend.auth import hash_password, create_session
from backend.config import settings

engine = create_engine("sqlite:///./test_items.db", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_ROOT", str(tmp_path))
    Base.metadata.create_all(bind=engine)
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db

    db = TestingSessionLocal()
    user = User(email="c@example.com", password_hash=hash_password("Password123!"), display_name="C")
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_session(db, user.id, "TestAgent")
    items_dir = tmp_path / "users" / str(user.id) / "items"
    items_dir.mkdir(parents=True)
    db.close()

    c = TestClient(app)
    c.cookies.set("session", token)
    yield c, items_dir

    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous
    Base.metadata.drop_all(bind=engine)


def test_manual_garment_needs_no_photo(client):
    """PRD OOTD-12: type in a garment you never photographed."""
    c, _ = client
    res = c.post("/api/items", json={
        "name": "Black jeans", "category": "bottomwear", "is_manual": 1,
    })
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["stored_name"] == ""
    assert body["bytes"] == 0


def test_size_is_read_from_disk_not_the_request(client):
    c, items_dir = client
    (items_dir / "real.png").write_bytes(b"x" * 321)

    res = c.post("/api/items", json={
        "name": "Shirt", "category": "topwear",
        "stored_name": "real.png", "bytes": 99_999_999,
    })
    assert res.status_code == 200, res.text
    assert res.json()["bytes"] == 321, "client-supplied byte count was trusted"


def test_image_that_does_not_exist_is_rejected(client):
    c, _ = client
    res = c.post("/api/items", json={
        "name": "Ghost", "category": "shoes", "stored_name": "nope.png",
    })
    assert res.status_code == 400


def test_unknown_category_is_rejected(client):
    """The closet filters on a fixed set; a free-text category breaks them."""
    c, _ = client
    assert c.post("/api/items", json={"name": "X", "category": "banana"}).status_code == 422
    assert c.patch("/api/items/1", json={"category": "banana"}).status_code == 422


def test_blank_name_is_rejected(client):
    c, _ = client
    assert c.post("/api/items", json={"name": "", "category": "other"}).status_code == 422
