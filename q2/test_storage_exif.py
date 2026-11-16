import io
import pytest
from PIL import Image
from backend.storage import validate_and_store_original, get_user_storage_dir
from fastapi import HTTPException
from pathlib import Path


def test_exif_metadata_stripped():
    """Verify that EXIF metadata (GPS/camera tags) is stripped during storage."""
    img = Image.new("RGB", (100, 100), color=(200, 100, 50))
    exif = img.getexif()
    exif[0x010e] = "Sensitive GPS Location Metadata"
    exif[0x010f] = "Camera Manufacturer Brand"

    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    raw_bytes = buf.getvalue()

    stored_name, file_bytes, img_clean, is_duplicate = validate_and_store_original(raw_bytes, "image/jpeg", user_id=999)

    # Check saved file on disk
    saved_file = get_user_storage_dir(999, "originals") / stored_name
    saved_img = Image.open(saved_file)
    clean_exif = saved_img.getexif()
    assert len(clean_exif) == 0, "EXIF metadata was not stripped from disk image!"


def test_invalid_file_type_rejected():
    """Verify that non-image content types are rejected with 415."""
    fake_pdf = b"%PDF-1.4 fake pdf content"
    with pytest.raises(HTTPException) as exc:
        validate_and_store_original(fake_pdf, "application/pdf", user_id=999)
    assert exc.value.status_code == 415


def test_file_size_exceeded_rejected():
    """Verify that files exceeding the maximum size limit are rejected with 413."""
    too_large = b"0" * (11 * 1024 * 1024)  # 11 MB
    with pytest.raises(HTTPException) as exc:
        validate_and_store_original(too_large, "image/jpeg", user_id=999)
    assert exc.value.status_code == 413


def test_corrupted_image_rejected():
    """Verify that corrupt byte sequences fail image verification with 400."""
    corrupt_bytes = b"NOT_A_REAL_JPEG_IMAGE_HEADER_12345"
    with pytest.raises(HTTPException) as exc:
        validate_and_store_original(corrupt_bytes, "image/jpeg", user_id=999)
    assert exc.value.status_code == 400


def test_decompression_bomb_rejected():
    """Verify that excessive pixel resolution is blocked to prevent DoS."""
    huge_img = Image.new("RGB", (10000, 6000))  # 60 million pixels > 50M limit
    buf = io.BytesIO()
    huge_img.save(buf, format="JPEG")
    raw = buf.getvalue()

    with pytest.raises(HTTPException) as exc:
        validate_and_store_original(raw, "image/jpeg", user_id=999)
    assert exc.value.status_code == 400
    assert "resolution is too large" in exc.value.detail
