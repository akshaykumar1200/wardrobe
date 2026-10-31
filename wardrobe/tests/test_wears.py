import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database import Base, get_db
from backend.models import User, Item, WearEvent
from backend.auth import hash_password, create_session

engine = create_engine("sqlite:///./test_wears.db", connect_args={"check_same_thread": False})
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
    user = User(email="wear@example.com", password_hash=hash_password("Password123!"))
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_session(db, user.id, "TestAgent")
    first = Item(user_id=user.id, name="Blue shirt", category="topwear", stored_name="", is_manual=1)
    second = Item(user_id=user.id, name="Black jeans", category="bottomwear", stored_name="", is_manual=1)
    db.add_all([first, second])
    db.commit()
    db.refresh(first)
    db.refresh(second)
    db.close()
    c = TestClient(app)
    c.cookies.set("session", token)
    yield c, first.id, second.id
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous
    Base.metadata.drop_all(bind=engine)


def test_same_composition_same_day_is_idempotent(client):
    c, first_id, second_id = client
    body = {"item_ids": [first_id, second_id], "worn_on": "2026-10-20"}
    first = c.post("/api/wears", json=body)
    second = c.post("/api/wears", json={**body, "item_ids": [second_id, first_id]})
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["already_recorded"] is False
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["already_recorded"] is True
    db = TestingSessionLocal()
    try:
        assert db.query(WearEvent).count() == 1
    finally:
        db.close()


def test_same_composition_different_day_creates_event(client):
    c, first_id, second_id = client
    ids = [first_id, second_id]
    a = c.post("/api/wears", json={"item_ids": ids, "worn_on": "2026-10-20"})
    b = c.post("/api/wears", json={"item_ids": ids, "worn_on": "2026-10-21"})
    assert a.status_code == b.status_code == 200
    assert a.json()["id"] != b.json()["id"]


def test_stats_count_and_undo(client):
    c, first_id, second_id = client
    first = c.post("/api/wears", json={"item_ids": [first_id], "worn_on": "2026-10-20"}).json()
    c.post("/api/wears", json={"item_ids": [first_id], "worn_on": "2026-10-21"})
    stats = c.get("/api/wears/stats")
    assert stats.status_code == 200
    assert stats.json()["counts"][str(first_id)] == 2
    assert stats.json()["last_worn"][str(first_id)] == "2026-10-21"
    assert c.delete(f"/api/wears/{first['id']}").status_code == 200
    assert c.get("/api/wears/stats").json()["counts"][str(first_id)] == 1
