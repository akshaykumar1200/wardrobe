from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database import Base, get_db
from backend.models import User, Item
from backend.auth import hash_password, create_session

engine = create_engine("sqlite:///./test_scoring.db", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    Base.metadata.create_all(bind=engine)
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr("backend.scoring.settings.STORAGE_ROOT", str(tmp_path))
    db = TestingSessionLocal()
    user = User(email="scoring@example.com", password_hash=hash_password("Password123!"))
    other = User(email="other-scoring@example.com", password_hash=hash_password("Password123!"))
    db.add_all([user, other])
    db.commit()
    db.refresh(user)
    db.refresh(other)
    token = create_session(db, user.id, "TestAgent")

    items = [
        Item(user_id=user.id, name="Blue shirt", category="topwear", stored_name="", color="#4169e1", is_manual=1),
        Item(user_id=user.id, name="Tan trousers", category="bottomwear", stored_name="", color="#d2b48c", is_manual=1),
        Item(user_id=user.id, name="Black shoes", category="shoes", stored_name="", color="#111111", is_manual=1),
        Item(user_id=user.id, name="Photo jacket", category="topwear", stored_name="photo.png", color=None),
        Item(user_id=other.id, name="Private garment", category="topwear", stored_name="", color="#ffffff", is_manual=1),
    ]
    db.add_all(items)
    db.commit()
    for item in items:
        db.refresh(item)
    ids = {item.name: item.id for item in items}
    ids["user_id"] = user.id
    db.close()

    photo_path = Path(tmp_path) / "users" / str(user.id) / "items" / "photo.png"
    photo_path.parent.mkdir(parents=True)
    Image.new("RGBA", (12, 16), (30, 80, 160, 255)).save(photo_path)

    c = TestClient(app)
    c.cookies.set("session", token)
    yield c, ids
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous
    Base.metadata.drop_all(bind=engine)


def test_score_owned_garments_returns_scoring_result(client):
    c, ids = client
    res = c.post("/api/outfits/score", json={"item_ids": [ids["Photo jacket"], ids["Tan trousers"], ids["Black shoes"]]})
    assert res.status_code == 200, res.text
    assert 0 <= res.json()["score"] <= 100
    assert res.json()["verdict"]


def test_score_rejects_another_users_item(client):
    c, ids = client
    res = c.post("/api/outfits/score", json={"item_ids": [ids["Blue shirt"], ids["Private garment"]]})
    assert res.status_code == 400
    assert res.json()["detail"] == "No such garment in your wardrobe"


def test_score_rejects_only_one_scorable_garment(client):
    c, ids = client
    res = c.post("/api/outfits/score", json={"item_ids": [ids["Blue shirt"]]})
    assert res.status_code == 400
    assert res.json()["detail"] == "Need two scorable garments"


def test_recommendations_explain_missing_bottomwear(client):
    c, ids = client
    db = TestingSessionLocal()
    try:
        db.query(Item).filter(Item.id == ids["Tan trousers"]).delete()
        db.commit()
    finally:
        db.close()
    res = c.get("/api/outfits/recommendations")
    assert res.status_code == 200, res.text
    assert res.json() == {
        "suggestions": [],
        "guidance": "Add at least one top and one bottom.",
    }


def test_recommendations_have_deterministic_order(client):
    c, ids = client
    db = TestingSessionLocal()
    try:
        # Add a second top so several combinations compete for the result list.
        db.add(Item(user_id=ids["user_id"], name="Green shirt", category="topwear", stored_name="", color="#228b22", is_manual=1))
        db.commit()
    finally:
        db.close()
    first = c.get("/api/outfits/recommendations?limit=5")
    second = c.get("/api/outfits/recommendations?limit=5")
    assert first.status_code == second.status_code == 200
    assert first.json()["suggestions"] == second.json()["suggestions"]


def test_manual_garment_with_color_can_be_scored(client):
    c, ids = client
    res = c.post("/api/outfits/score", json={"item_ids": [ids["Blue shirt"], ids["Tan trousers"]]})
    assert res.status_code == 200, res.text
    assert res.json()["verdict"]
