import pytest
from pathlib import Path
from PIL import Image
from backend.models import Item
from backend.config import settings


def test_create_item_success(auth_client_a, user_a, db_session):
    payload = {
        "name": "Vintage Denim Jacket",
        "category": "topwear",
        "stored_name": "denim_jacket_123.png",
        "color": "#2c4c64",
        "bytes": 50000,
        "is_manual": 1
    }
    res = auth_client_a.post("/api/items", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Vintage Denim Jacket"
    assert data["category"] == "topwear"
    assert data["user_id"] == user_a.id
    assert data["image_url"] == "/api/images/item/denim_jacket_123.png"

    item = db_session.query(Item).filter(Item.id == data["id"]).first()
    assert item is not None
    assert item.user_id == user_a.id


def test_list_items_empty(auth_client_a):
    res = auth_client_a.get("/api/items")
    assert res.status_code == 200
    assert res.json() == []


def test_list_items_category_filter(auth_client_a, user_a, db_session):
    i1 = Item(user_id=user_a.id, name="White Tee", category="topwear", stored_name="tee.png")
    i2 = Item(user_id=user_a.id, name="Black Jeans", category="bottomwear", stored_name="jeans.png")
    i3 = Item(user_id=user_a.id, name="Sneakers", category="shoes", stored_name="shoes.png")
    db_session.add_all([i1, i2, i3])
    db_session.commit()

    # Filter category=topwear
    res_top = auth_client_a.get("/api/items?category=topwear")
    assert res_top.status_code == 200
    items_top = res_top.json()
    assert len(items_top) == 1
    assert items_top[0]["name"] == "White Tee"

    # Filter category=all
    res_all = auth_client_a.get("/api/items?category=all")
    assert res_all.status_code == 200
    assert len(res_all.json()) == 3


def test_list_items_search_filter(auth_client_a, user_a, db_session):
    i1 = Item(user_id=user_a.id, name="Oversized Linen Shirt", category="topwear", stored_name="shirt.png")
    i2 = Item(user_id=user_a.id, name="Silk Scarf", category="accessories", stored_name="scarf.png")
    db_session.add_all([i1, i2])
    db_session.commit()

    res = auth_client_a.get("/api/items?q=linen")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["name"] == "Oversized Linen Shirt"


def test_get_own_item_success(auth_client_a, user_a, db_session):
    item = Item(user_id=user_a.id, name="Cashmere Sweater", category="topwear", stored_name="sweater.png")
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)

    res = auth_client_a.get(f"/api/items/{item.id}")
    assert res.status_code == 200
    assert res.json()["name"] == "Cashmere Sweater"


def test_update_item_success(auth_client_a, user_a, db_session):
    item = Item(user_id=user_a.id, name="Old Name", category="topwear", stored_name="item.png", color="#000000")
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)

    res = auth_client_a.patch(
        f"/api/items/{item.id}",
        json={"name": "Wool Overcoat", "category": "other", "color": "#7d8c71"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Wool Overcoat"
    assert data["category"] == "other"
    assert data["color"] == "#7d8c71"


def test_delete_item_success(auth_client_a, user_a, db_session):
    # Create test physical file
    dest_dir = Path(settings.STORAGE_ROOT) / "users" / str(user_a.id) / "items"
    dest_dir.mkdir(parents=True, exist_ok=True)
    stored_name = "to_delete.png"
    img_path = dest_dir / stored_name
    Image.new("RGBA", (10, 10)).save(img_path)

    item = Item(user_id=user_a.id, name="Item To Delete", category="topwear", stored_name=stored_name)
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)

    res = auth_client_a.delete(f"/api/items/{item.id}")
    assert res.status_code == 200
    assert res.json()["deleted"] == item.id

    # Verify DB record is removed
    assert db_session.query(Item).filter(Item.id == item.id).first() is None
    # Verify file on disk is unlinked
    assert not img_path.exists()
