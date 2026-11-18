import base64
import io

import pytest
import numpy as np
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
    from backend.auth import limiter
    from backend.routers import cutout
    cutout._jobs.clear()
    limiter.reset()   # the file posts more than the 20/minute limit allows
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


def test_mask_returns_padded_cropped_grayscale_png(client, monkeypatch):
    from backend.routers import cutout

    matte = np.zeros((8, 10), dtype=np.float32)
    matte[1:5, 2:6] = 1.0
    monkeypatch.setattr(cutout, "subject_matte", lambda img: matte)
    monkeypatch.setattr(settings, "CUTOUT_API_KEY", "shared-secret")
    c, _, storage_root = client
    response = c.post("/api/cutout/mask", files={"image": ("photo.png", _upload_bytes(), "image/png")},
                      headers={"X-Cutout-Key": "shared-secret"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["width"], body["height"]) == (10, 8)
    assert body["crop_box"] == [1, 0, 7, 6]
    decoded = base64.b64decode(body["mask_png_base64"])
    with Image.open(io.BytesIO(decoded)) as mask:
        assert mask.mode == "L"
        assert mask.size == (6, 6)
        assert mask.getpixel((1, 1)) == 255
    assert not storage_root.exists()


def test_mask_key_config_and_auth_statuses(client, monkeypatch):
    monkeypatch.setattr(settings, "CUTOUT_API_KEY", "shared-secret")
    c, _, _ = client
    files = {"image": ("photo.png", _upload_bytes(), "image/png")}
    assert c.post("/api/cutout/mask", files=files).status_code == 401
    assert c.post("/api/cutout/mask", files=files, headers={"X-Cutout-Key": "wrong"}).status_code == 401
    monkeypatch.setattr(settings, "CUTOUT_API_KEY", "")
    assert c.post("/api/cutout/mask", files=files).status_code == 503


def test_mask_unavailable_when_matte_is_none(client, monkeypatch):
    from backend.routers import cutout

    monkeypatch.setattr(cutout, "subject_matte", lambda img: None)
    monkeypatch.setattr(settings, "CUTOUT_API_KEY", "shared-secret")
    c, _, _ = client
    response = c.post("/api/cutout/mask", files={"image": ("photo.png", _upload_bytes(), "image/png")},
                      headers={"X-Cutout-Key": "shared-secret"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Background removal is not available."


def test_mask_rejects_empty_matte(client, monkeypatch):
    from backend.routers import cutout

    monkeypatch.setattr(cutout, "subject_matte", lambda img: np.zeros((8, 10), dtype=np.float32))
    monkeypatch.setattr(settings, "CUTOUT_API_KEY", "shared-secret")
    c, _, _ = client
    response = c.post("/api/cutout/mask", files={"image": ("photo.png", _upload_bytes(), "image/png")},
                      headers={"X-Cutout-Key": "shared-secret"})
    assert response.status_code == 422
    assert response.json()["detail"] == "No subject found."


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


# --- Google Flow pictures (backend/flow_shot.py) ---

def _post_with_flow(c, monkeypatch, fake_draw):
    from backend import flow_shot
    from backend.routers import cutout
    monkeypatch.setattr(settings, "FLOW_URL", "http://127.0.0.1:8787")
    monkeypatch.setattr(settings, "TRYOFF_PYTHON", "")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(settings, "CUTOUT_API_KEY", "shared-secret")
    monkeypatch.setattr(cutout, "extract_garments", _fake_extract_big_top)
    monkeypatch.setattr(flow_shot, "_draw", fake_draw)
    flow_shot._shots.clear()
    response = c.post("/api/cutout", files={"image": ("photo.png", _upload_bytes(), "image/png")},
                      headers={"X-Cutout-Key": "shared-secret"})
    assert response.status_code == 200, response.text
    return {i["name"]: i for i in response.json()["items"]}


def _poll_flatlay(c, shot_id, tries=50):
    import time
    for _ in range(tries):
        body = c.get(f"/api/cutout/flatlay/{shot_id}", headers={"X-Cutout-Key": "shared-secret"})
        if body.status_code != 200 or body.json()["status"] != "pending":
            return body
        time.sleep(0.02)
    return body


def test_cutout_returns_at_once_and_flow_picture_is_fetched_later(client, monkeypatch):
    import asyncio
    green = _upload_bytes(Image.new("RGB", (8, 8), (0, 200, 0)))
    drawn_for = []

    async def fake_draw(png, name):
        drawn_for.append(name)
        await asyncio.sleep(0.05)
        return green

    with TestClient(app) as c:      # one event loop for both requests, so the background picture survives
        items = _post_with_flow(c, monkeypatch, fake_draw)
        assert items["Top"]["png_base64"]                     # the cut-out comes back straight away
        assert items["Shoes"]["flatlay_id"] is None           # shoes are not redrawn
        body = _poll_flatlay(c, items["Top"]["flatlay_id"])
    assert body.json()["status"] == "ready"
    assert base64.b64decode(body.json()["png_base64"]) == green
    assert drawn_for == ["Top"]


def test_failed_flow_picture_reports_failed_and_unknown_id_is_404(client, monkeypatch):
    async def fake_draw(png, name):
        return None

    with TestClient(app) as c:
        items = _post_with_flow(c, monkeypatch, fake_draw)
        assert _poll_flatlay(c, items["Top"]["flatlay_id"]).json() == {"status": "failed"}
        assert c.get("/api/cutout/flatlay/nope", headers={"X-Cutout-Key": "shared-secret"}).status_code == 404
        assert c.get(f"/api/cutout/flatlay/{items['Top']['flatlay_id']}").status_code == 401


def test_no_flow_url_means_no_flatlay_id(client, monkeypatch, patched_extract):
    monkeypatch.setattr(settings, "FLOW_URL", "")
    monkeypatch.setattr(settings, "CUTOUT_API_KEY", "shared-secret")
    c, _, _ = client
    response = c.post("/api/cutout", files={"image": ("photo.png", _upload_bytes(), "image/png")},
                      headers={"X-Cutout-Key": "shared-secret"})
    assert all(i["flatlay_id"] is None for i in response.json()["items"])


def test_draw_speaks_flow_mcps_api(monkeypatch, tmp_path):
    """Upload -> generate -> wait until done, with the token header, then reads the finished file."""
    import asyncio
    import json
    import httpx
    from backend import flow_shot

    token = tmp_path / "token"
    token.write_text("tok123\n")
    finished = tmp_path / "scene-01.png"   # PNG so the colour check is exact (JPEG shifts it)
    Image.new("RGB", (6, 6), (0, 0, 255)).save(finished)
    monkeypatch.setattr(flow_shot, "TOKEN_FILE", token)
    monkeypatch.setattr(settings, "FLOW_URL", "http://127.0.0.1:8787/")
    calls, waits = [], iter([{"status": "running"}, {"status": "done", "files": [str(finished)]}])

    def handler(request):
        assert request.headers["x-flow-token"] == "tok123"
        calls.append(request.url.path)
        if request.url.path == "/api/upload":
            with Image.open(io.BytesIO(request.content)) as ref:
                assert ref.format == "JPEG" and ref.getpixel((0, 0)) == (255, 255, 255)  # transparent -> white
            return httpx.Response(200, json={"path": "C:/up/garment.jpg"})
        body = json.loads(request.content)
        if request.url.path == "/api/generate":
            scene = body["scenes"][0]
            assert scene["reference_images"] == ["C:/up/garment.jpg"]
            assert scene["type"] == "image" and scene["max_credits"] == 0
            return httpx.Response(200, json={"jobs": [{"id": "j1"}]})
        assert body["job_ids"] == ["j1"]
        return httpx.Response(200, json={"finished": True, "jobs": [{"id": "j1", **next(waits)}]})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(flow_shot.httpx, "AsyncClient",
                        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    cutout_png = _upload_bytes(Image.new("RGBA", (4, 4), (0, 0, 0, 0)))
    png = asyncio.run(flow_shot._draw(cutout_png, "Top"))
    assert calls == ["/api/upload", "/api/generate", "/api/wait", "/api/wait"]
    assert Image.open(io.BytesIO(png)).getpixel((0, 0)) == (0, 0, 255)


def test_existing_cutout_can_start_a_flow_picture(client, monkeypatch):
    """A re-uploaded photo's saved piece gets its clean picture from the cut-out it already has."""
    from backend import flow_shot
    got = []

    async def fake_draw(png, name):
        got.append((Image.open(io.BytesIO(png)).mode, name))
        return b"\x89PNG-fake"

    monkeypatch.setattr(settings, "FLOW_URL", "http://127.0.0.1:8787")
    monkeypatch.setattr(settings, "CUTOUT_API_KEY", "shared-secret")
    monkeypatch.setattr(flow_shot, "_draw", fake_draw)
    cut = _upload_bytes(Image.new("RGBA", (6, 6), (0, 0, 0, 0)))
    with TestClient(app) as c:
        started = c.post("/api/cutout/flatlay", data={"name": "Green Tee"},
                         files={"image": ("cut.png", cut, "image/png")}, headers={"X-Cutout-Key": "shared-secret"})
        assert started.status_code == 200, started.text
        assert _poll_flatlay(c, started.json()["flatlay_id"]).json()["status"] == "ready"
        assert c.post("/api/cutout/flatlay", files={"image": ("cut.png", cut, "image/png")}).status_code == 401
        monkeypatch.setattr(settings, "FLOW_URL", "")
        assert c.post("/api/cutout/flatlay", files={"image": ("cut.png", cut, "image/png")},
                      headers={"X-Cutout-Key": "shared-secret"}).status_code == 503
    assert got == [("RGBA", "Green Tee")]   # transparency reaches Flow, so the reference is on white
