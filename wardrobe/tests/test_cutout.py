import base64
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.auth import create_session, hash_password
from backend.config import settings
from backend.database import Base
from backend.main import app
from backend.models import Blob, User
from backend.storage import save_garment_crop, use_crop_db


engine = create_engine("sqlite:///./test_cutout.db", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_ROOT", str(tmp_path / "storage"))
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    user = User(email="cutout@example.com", password_hash=hash_password("Password123!"), display_name="Cutout")
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_session(db, user.id, "test")
    db.close()
    c = TestClient(app)
    yield c, token, tmp_path / "storage"
    Base.metadata.drop_all(bind=engine)


def _upload_bytes(image=None):
    image = image or Image.new("RGB", (10, 8), (20, 40, 60))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _fake_extract(img, user_id, complete=False):
    assert user_id == 0
    assert complete  # the service always asks for hidden parts to be painted in
    entries = []
    for name, color, size in (("Top", "#ff0000", (7, 5)), ("Shoes", "#0000ff", (4, 6))):
        crop = Image.new("RGBA", size, (255, 0, 0, 123))
        stored_name, byte_count = save_garment_crop(crop, user_id)
        entries.append({
            "name": name,
            "category": "topwear" if name == "Top" else "shoes",
            "stored_name": stored_name,
            "color": color,
            "bytes": byte_count,
            "confidence": 0.91,
            "image_url": f"/api/images/item/{stored_name}",
        })
    return {"items": entries, "notice": None}


@pytest.fixture
def patched_extract(monkeypatch):
    from backend.routers import cutout
    monkeypatch.setattr(cutout, "extract_garments", _fake_extract)


def test_cutout_key_config_and_auth_statuses(client, monkeypatch, patched_extract):
    c, _, _ = client
    payload = {"image": ("photo.png", _upload_bytes(), "image/png")}
    monkeypatch.setattr(settings, "CUTOUT_API_KEY", "")
    assert c.post("/api/cutout", files=payload).status_code == 503

    monkeypatch.setattr(settings, "CUTOUT_API_KEY", "shared-secret")
    assert c.post("/api/cutout", files=payload).status_code == 401
    assert c.post("/api/cutout", files=payload, headers={"X-Cutout-Key": "wrong"}).status_code == 401


@pytest.mark.parametrize("auth_kind", ["cookie", "bearer"])
def test_session_auth_does_not_replace_cutout_key(client, monkeypatch, patched_extract, auth_kind):
    c, token, _ = client
    monkeypatch.setattr(settings, "CUTOUT_API_KEY", "shared-secret")
    files = {"image": ("photo.png", _upload_bytes(), "image/png")}
    if auth_kind == "cookie":
        c.cookies.set("session", token)
        response = c.post("/api/cutout", files=files)
    else:
        response = c.post("/api/cutout", files=files, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_valid_key_returns_transparent_pngs_without_persisting(client, monkeypatch, patched_extract):
    c, _, storage_root = client
    monkeypatch.setattr(settings, "CUTOUT_API_KEY", "shared-secret")
    files = {"image": ("photo.png", _upload_bytes(), "image/png")}
    before_files = set(storage_root.rglob("*")) if storage_root.exists() else set()
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as db:
        before_blobs = db.query(Blob).count()

    response = c.post("/api/cutout", files=files, headers={"X-Cutout-Key": "shared-secret"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["notice"] is None
    assert len(body["items"]) == 2
    assert isinstance(body["seconds"], float)
    for item, size in zip(body["items"], ((7, 5), (4, 6))):
        assert "stored_name" not in item
        assert (item["width"], item["height"]) == size
        decoded = base64.b64decode(item["png_base64"])
        with Image.open(io.BytesIO(decoded)) as png:
            assert png.format == "PNG"
            assert png.mode == "RGBA"
            assert png.size == size
    with TestingSessionLocal() as db:
        assert db.query(Blob).count() == before_blobs
    after_files = set(storage_root.rglob("*")) if storage_root.exists() else set()
    assert after_files == before_files


def test_save_crop_outside_capture_still_persists(client):
    _, _, storage_root = client
    db = TestingSessionLocal()
    crop = Image.new("RGBA", (3, 4), (1, 2, 3, 127))
    with use_crop_db(db):
        name, size = save_garment_crop(crop, 77)
    path = storage_root / "users" / "77" / "items" / name
    assert path.is_file()
    assert path.stat().st_size == size
    db.close()


@pytest.mark.parametrize("case,expected", [("oversized", 413), ("not_image", 400)])
def test_upload_validation_matches_upload_route(client, monkeypatch, patched_extract, case, expected):
    c, _, _ = client
    monkeypatch.setattr(settings, "CUTOUT_API_KEY", "shared-secret")
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 1)
    payload = b"x" * (1024 * 1024 + 1) if case == "oversized" else b"not an image"
    response = c.post(
        "/api/cutout",
        files={"image": ("photo", payload, "image/png")},
        headers={"X-Cutout-Key": "shared-secret"},
    )
    assert response.status_code == expected


@pytest.fixture(autouse=True)
def fresh_jobs():
    from backend.routers import cutout
    cutout._jobs.clear()
    yield
    cutout._jobs.clear()


def test_identical_photos_share_one_run(client, monkeypatch):
    import threading
    import time as _time
    from backend.routers import cutout

    calls = []
    def slow_extract(img, user_id, complete=False):
        calls.append(img.size)
        _time.sleep(0.5)   # long enough for both requests to overlap
        return _fake_extract(img, user_id, complete)
    monkeypatch.setattr(cutout, "extract_garments", slow_extract)
    monkeypatch.setattr(settings, "CUTOUT_API_KEY", "shared-secret")
    headers = {"X-Cutout-Key": "shared-secret"}

    _, _, _ = client
    with TestClient(app) as c:
        def post(image, out):
            out.append(c.post("/api/cutout", files={"image": ("p.png", _upload_bytes(image), "image/png")},
                              headers=headers))
        same = []
        threads = [threading.Thread(target=post, args=(None, same)) for _ in range(3)]
        for t in threads: t.start()
        for t in threads: t.join()
        assert [r.status_code for r in same] == [200, 200, 200]
        assert len({r.text for r in same}) == 1
        assert len(calls) == 1                       # three callers, one run

        post(None, same)                             # a repeat soon after is reused too
        assert len(calls) == 1
        other = []
        post(Image.new("RGB", (10, 8), (200, 0, 0)), other)
        assert other[0].status_code == 200 and len(calls) == 2


def test_failed_run_is_not_reused(client, monkeypatch):
    from backend.routers import cutout
    attempts = []
    def flaky(img, user_id, complete=False):
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("model crashed")
        return _fake_extract(img, user_id, complete)
    monkeypatch.setattr(cutout, "extract_garments", flaky)
    monkeypatch.setattr(settings, "CUTOUT_API_KEY", "shared-secret")
    headers = {"X-Cutout-Key": "shared-secret"}
    with TestClient(app, raise_server_exceptions=False) as c:
        files = lambda: {"image": ("p.png", _upload_bytes(), "image/png")}
        assert c.post("/api/cutout", files=files(), headers=headers).status_code == 500
        assert c.post("/api/cutout", files=files(), headers=headers).status_code == 200
    assert len(attempts) == 2


# --- product picture of the top (TryOffDiff) ---

def _fake_extract_big_top(img, user_id, complete=False):
    entries = []
    for name, category, size in (("Top", "topwear", (20, 20)), ("Shoes", "shoes", (4, 6))):
        stored_name, byte_count = save_garment_crop(Image.new("RGBA", size, (28, 65, 58, 255)), user_id)
        entries.append({"name": name, "category": category, "stored_name": stored_name, "color": "#1c413a",
                        "bytes": byte_count, "confidence": 0.9, "image_url": f"/api/images/item/{stored_name}"})
    return {"items": entries, "notice": None}


# Stands in for tryoff/run_tryoff.py: a bright green shirt-sized block on a pale background.
_FAKE_TRYOFF = """
import sys
from PIL import Image, ImageDraw
src, dst = sys.argv[3].split(":")
Image.open(src).close()
img = Image.new("RGB", (128, 128), (240, 240, 238))
ImageDraw.Draw(img).rectangle([30, 20, 97, 109], fill=(40, 200, 140))
img.save(dst)
"""


def _post_with_tryoff(client, monkeypatch, tmp_path, script_text):
    import sys
    from backend import product_shot
    from backend.routers import cutout
    script = tmp_path / "fake_tryoff.py"
    script.write_text(script_text)
    monkeypatch.setattr(product_shot, "SCRIPT", script)
    monkeypatch.setattr(settings, "TRYOFF_PYTHON", sys.executable)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")   # no network from tests
    monkeypatch.setattr(settings, "CUTOUT_API_KEY", "shared-secret")
    monkeypatch.setattr(cutout, "extract_garments", _fake_extract_big_top)
    c, _, _ = client
    response = c.post("/api/cutout", files={"image": ("photo.png", _upload_bytes(), "image/png")},
                      headers={"X-Cutout-Key": "shared-secret"})
    assert response.status_code == 200, response.text
    return {i["name"]: i for i in response.json()["items"]}


def test_top_becomes_a_drawn_product_picture_in_its_real_colour(client, monkeypatch, tmp_path):
    items = _post_with_tryoff(client, monkeypatch, tmp_path, _FAKE_TRYOFF)
    assert (items["Shoes"]["width"], items["Shoes"]["height"]) == (4, 6)   # only the top is drawn
    top = Image.open(io.BytesIO(base64.b64decode(items["Top"]["png_base64"])))
    assert top.mode == "RGBA"
    assert abs(top.width - 68) <= 4 and abs(top.height - 90) <= 4          # the drawn block, cropped tight
    r, g, b, a = top.getpixel((top.width // 2, top.height // 2))
    assert a == 255
    assert max(abs(r - 28), abs(g - 65), abs(b - 58)) <= 6                 # real colour, not the bright green


def test_failed_drawing_keeps_the_real_cutout(client, monkeypatch, tmp_path):
    items = _post_with_tryoff(client, monkeypatch, tmp_path, "import sys; sys.exit(1)")
    assert (items["Top"]["width"], items["Top"]["height"]) == (20, 20)


def test_two_tops_keep_their_cutouts(client, monkeypatch, tmp_path):
    from backend.routers import cutout

    def two_tops(img, user_id, complete=False):
        result = _fake_extract_big_top(img, user_id, complete)
        result["items"][1]["category"] = "topwear"
        return result
    items = _post_with_tryoff(client, monkeypatch, tmp_path, _FAKE_TRYOFF)   # sets everything up
    cutout._jobs.clear()
    monkeypatch.setattr(cutout, "extract_garments", two_tops)
    c, _, _ = client
    body = c.post("/api/cutout", files={"image": ("photo.png", _upload_bytes(), "image/png")},
                  headers={"X-Cutout-Key": "shared-secret"}).json()
    assert [(i["width"], i["height"]) for i in body["items"]] == [(20, 20), (4, 6)]


def test_drawn_top_is_not_also_sent_to_gemini(client, monkeypatch, tmp_path):
    from backend.routers import cutout
    sent = []

    async def fake_flatlay(png, name, color):
        sent.append(name)
        return None
    monkeypatch.setattr(cutout, "generate_flatlay", fake_flatlay)
    monkeypatch.setattr(settings, "FLATLAY_ENABLED", True)
    items = _post_with_tryoff(client, monkeypatch, tmp_path, _FAKE_TRYOFF)
    assert items["Top"]["is_flatlay"] is True       # drawn by TryOffDiff
    assert "Top" not in sent
