import pytest
from pathlib import Path
from PIL import Image
from backend.models import Item
from backend.config import settings


@pytest.fixture
def item_user_a(db_session, user_a):
    # Ensure physical dummy file exists in user_a storage
    dest_dir = Path(settings.STORAGE_ROOT) / "users" / str(user_a.id) / "items"
    dest_dir.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", (50, 50), color=(100, 150, 200, 255))
    stored_name = "user_a_test_shirt.png"
    img.save(dest_dir / stored_name, "PNG")

    item = Item(
        user_id=user_a.id,
        name="User A Blue Linen Shirt",
        category="topwear",
        stored_name=stored_name,
        color="#6496c8",
        bytes=1024,
        is_manual=0
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


def test_cross_user_get_item_returns_404(auth_client_b, item_user_a):
    """User B attempts to fetch User A's item. Must return 404 to avoid leaking existence."""
    res = auth_client_b.get(f"/api/items/{item_user_a.id}")
    assert res.status_code == 404
    assert res.json()["detail"] == "Item not found"


def test_cross_user_patch_item_returns_404(auth_client_b, item_user_a, db_session):
    """User B attempts to modify User A's item. Must return 404 and leave DB untouched."""
    res = auth_client_b.patch(
        f"/api/items/{item_user_a.id}",
        json={"name": "Hacked Name by User B"}
    )
    assert res.status_code == 404

    db_session.refresh(item_user_a)
    assert item_user_a.name == "User A Blue Linen Shirt"


def test_cross_user_delete_item_returns_404(auth_client_b, item_user_a, db_session):
    """User B attempts to delete User A's item. Must return 404 and leave record in DB."""
    res = auth_client_b.delete(f"/api/items/{item_user_a.id}")
    assert res.status_code == 404

    db_item = db_session.query(Item).filter(Item.id == item_user_a.id).first()
    assert db_item is not None


def test_cross_user_get_image_returns_404(auth_client_b, item_user_a):
    """User B attempts to retrieve User A's isolated garment image. Must return 404."""
    res = auth_client_b.get(f"/api/images/item/{item_user_a.stored_name}")
    assert res.status_code == 404


def test_unauthenticated_item_access_returns_401(client, item_user_a):
    """Anonymous client attempts to access items or image. Must return 401."""
    res1 = client.get("/api/items")
    assert res1.status_code == 401

    res2 = client.get(f"/api/items/{item_user_a.id}")
    assert res2.status_code == 401

    res3 = client.get(f"/api/images/item/{item_user_a.stored_name}")
    assert res3.status_code == 401


def test_image_path_traversal_blocked(auth_client_a):
    """Attempting path traversal via stored_name parameter must be rejected."""
    res = auth_client_a.get("/api/images/item/../../database.py")
    assert res.status_code in (400, 404)
