import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database import Base, get_db
from backend.models import User, Item, Outfit
from backend.auth import hash_password, create_session

engine = create_engine("sqlite:///./test_outfits.db", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    Base.metadata.create_all(bind=engine)
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    db = TestingSessionLocal()
    user = User(email="outfit@example.com", password_hash=hash_password("Password123!"))
    other = User(email="other-outfit@example.com", password_hash=hash_password("Password123!"))
    db.add_all([user, other])
    db.commit()
    db.refresh(user)
    db.refresh(other)
    token = create_session(db, user.id, "TestAgent")
    other_item = Item(user_id=other.id, name="Private garment", category="topwear", stored_name="", is_manual=1)
    item = Item(user_id=user.id, name="Blue shirt", category="topwear", stored_name="", is_manual=1)
    db.add_all([other_item, item])
    db.commit()
    db.refresh(item)
    db.refresh(other_item)
    db.close()
    c = TestClient(app)
    c.cookies.set("session", token)
    yield c, item.id, other_item.id
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous
    Base.metadata.drop_all(bind=engine)


def test_create_and_read_outfit_has_item_names(client):
    c, item_id, _ = client
    created = c.post("/api/outfits", json={"name": "Weekend", "item_ids": [item_id]})
    assert created.status_code == 200, created.text
    outfit_id = created.json()["id"]
    read = c.get(f"/api/outfits/{outfit_id}")
    assert read.status_code == 200
    assert read.json()["items"][0]["name"] == "Blue shirt"


def test_other_users_item_is_rejected(client):
    c, _, other_item_id = client
    res = c.post("/api/outfits", json={"name": "Nope", "item_ids": [other_item_id]})
    assert res.status_code == 400
    assert res.json()["detail"] == "No such garment in your wardrobe"


def test_deleting_outfit_preserves_items(client):
    c, item_id, _ = client
    outfit_id = c.post("/api/outfits", json={"name": "Weekend", "item_ids": [item_id]}).json()["id"]
    assert c.delete(f"/api/outfits/{outfit_id}").status_code == 200
    db = TestingSessionLocal()
    try:
        assert db.query(Item).filter(Item.id == item_id).one()
    finally:
        db.close()


def test_deleting_item_keeps_outfit_snapshot(client):
    c, item_id, _ = client
    outfit_id = c.post("/api/outfits", json={"name": "Weekend", "item_ids": [item_id]}).json()["id"]
    assert c.delete(f"/api/items/{item_id}").status_code == 200
    result = c.get(f"/api/outfits/{outfit_id}").json()["items"][0]
    assert result == {"item_id": None, "name": "Blue shirt", "available": False, "image_url": None}
