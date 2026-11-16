import pytest
from backend.models import Item, Upload


def test_non_admin_stats_forbidden(auth_client_a):
    """Regular users must receive 403 when trying to access admin stats."""
    res = auth_client_a.get("/api/admin/stats")
    assert res.status_code == 403
    assert "Admin access required" in res.json()["detail"]


def test_non_admin_users_forbidden(auth_client_a):
    """Regular users must receive 403 when trying to list users."""
    res = auth_client_a.get("/api/admin/users")
    assert res.status_code == 403


def test_admin_get_stats_success(auth_admin_client, user_a, user_b, db_session):
    """Admin receives aggregate system metrics."""
    # Seed items & uploads
    item1 = Item(user_id=user_a.id, name="Item 1", category="topwear", stored_name="i1.png", bytes=100)
    item2 = Item(user_id=user_b.id, name="Item 2", category="bottomwear", stored_name="i2.png", bytes=200)
    upload1 = Upload(user_id=user_a.id, stored_name="u1.jpg", bytes=500)
    db_session.add_all([item1, item2, upload1])
    db_session.commit()

    res = auth_admin_client.get("/api/admin/stats")
    assert res.status_code == 200
    data = res.json()
    assert data["total_users"] >= 3  # user_a, user_b, admin
    assert data["total_items"] >= 2
    assert data["total_uploads"] >= 1
    assert data["storage_bytes"] >= 800
    assert "topwear" in data["items_by_category"]


def test_admin_get_users_privacy(auth_admin_client, user_a):
    """Admin user directory returns metadata but never leaks password hashes or raw images."""
    res = auth_admin_client.get("/api/admin/users")
    assert res.status_code == 200
    users_list = res.json()
    assert len(users_list) >= 1

    for u in users_list:
        assert "password" not in u
        assert "password_hash" not in u
        assert "image_url" not in u
        assert "email" in u
        assert "item_count" in u
