import io
import pytest
import numpy as np
from PIL import Image
from backend.segmenter import _dominant_color


def test_dominant_color_computation():
    """Verify that _dominant_color extracts the correct hex string from RGB pixels."""
    rgb = np.zeros((10, 10, 3), dtype=np.uint8)
    # Fill with sage green RGB: (125, 140, 113) -> #7d8c71
    rgb[:, :] = [125, 140, 113]
    mask = np.ones((10, 10), dtype=bool)

    color_hex = _dominant_color(rgb, mask)
    assert color_hex == "#7d8c71"


def test_ai_segmentation_endpoint(auth_client_a):
    """Verify the /api/uploads endpoint accepts a multipart photo and returns segmentation candidates."""
    img = Image.new("RGB", (200, 300), color=(220, 220, 220))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    res = auth_client_a.post(
        "/api/uploads",
        files={"file": ("outfit.jpg", buf, "image/jpeg")}
    )
    assert res.status_code == 200
    data = res.json()
    assert "upload_id" in data
    assert "original_stored_name" in data
    assert "candidates" in data
    assert isinstance(data["candidates"], list)
