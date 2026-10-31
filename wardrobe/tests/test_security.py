import io
from pathlib import Path
import pytest
from PIL import Image, ImageOps
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database import Base, get_db
from backend.models import User, Item, Session as SessionModel
from backend.auth import hash_password, create_session
from backend.storage import validate_and_store_original
from backend.config import settings

# Setup Test Database
TEST_DB_URL = "sqlite:///./test_wardrobe.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_password_hashing():
    raw_pass = "MySecretPassword123!"
    hashed = hash_password(raw_pass)
    assert hashed != raw_pass
    assert "$argon2id$" in hashed


def test_cross_user_access_idor_prevention():
    db = TestingSessionLocal()

    # Create User A
    user_a = User(email="usera@example.com", password_hash=hash_password("Password123!"), display_name="User A")
    db.add(user_a)

    # Create User B
    user_b = User(email="userb@example.com", password_hash=hash_password("Password123!"), display_name="User B")
    db.add(user_b)
    db.commit()

    # Create Item for User A
    item_a = Item(
        user_id=user_a.id,
        name="User A Shirt",
        category="topwear",
        stored_name="test_item_a.png",
        color="#3b5b4c",
        bytes=100
    )
    db.add(item_a)
    db.commit()
    db.refresh(item_a)

    item_a_id = item_a.id
    item_a_stored_name = item_a.stored_name

    # Create Session for User B
    token_b = create_session(db, user_b.id, "TestAgent")
    db.close()

    client = TestClient(app)
    client.cookies.set("session", token_b)

    # 1. GET User A's item as User B -> Must be 404
    res_get = client.get(f"/api/items/{item_a_id}")
    assert res_get.status_code == 404, f"IDOR Vulnerability: GET returned {res_get.status_code}"

    # 2. PATCH User A's item as User B -> Must be 404
    res_patch = client.patch(f"/api/items/{item_a_id}", json={"name": "Hacked Name"})
    assert res_patch.status_code == 404, f"IDOR Vulnerability: PATCH returned {res_patch.status_code}"

    # 3. DELETE User A's item as User B -> Must be 404
    res_delete = client.delete(f"/api/items/{item_a_id}")
    assert res_delete.status_code == 404, f"IDOR Vulnerability: DELETE returned {res_delete.status_code}"

    # 4. GET User A's image as User B -> Must be 404
    res_img = client.get(f"/api/images/item/{item_a_stored_name}")
    assert res_img.status_code == 404, f"IDOR Vulnerability: Image GET returned {res_img.status_code}"


def test_exif_stripping():
    # Create an image with EXIF metadata
    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    exif = img.getexif()
    exif[0x010e] = "Test Image Description EXIF"  # Tag 270 ImageDescription
    exif_bytes = exif.tobytes()

    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif_bytes)
    raw_with_exif = buf.getvalue()

    stored_name, file_bytes, img_clean = validate_and_store_original(
        raw_with_exif, "image/jpeg", user_id=999
    )

    # Verify saved file on disk has zero EXIF metadata
    saved_file_path = Path("storage/users/999/originals") / stored_name
    saved_img = Image.open(saved_file_path)
    clean_exif = saved_img.getexif()
    assert len(clean_exif) == 0, "EXIF metadata was not stripped on disk!"


def test_cloud_mode_writes_no_original_to_disk(monkeypatch):
    """Ephemeral container storage should not receive originals."""
    monkeypatch.setattr(settings, "CLOUD_MODE", True)
    img = Image.new("RGB", (60, 60), color=(0, 128, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")

    stored_name, _, _ = validate_and_store_original(buf.getvalue(), "image/jpeg", user_id=998)

    on_disk = Path("storage/users/998/originals") / stored_name
    assert not on_disk.exists(), "wrote an original to storage that does not survive a restart"
