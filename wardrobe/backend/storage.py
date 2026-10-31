import hashlib
import io
from contextvars import ContextVar
from contextlib import contextmanager
from pathlib import Path
from PIL import Image, ImageOps
from fastapi import HTTPException

from backend.config import settings
from backend import crops

_crop_db: ContextVar[object | None] = ContextVar("crop_db", default=None)
_captured_crops: ContextVar[dict[str, bytes] | None] = ContextVar("captured_crops", default=None)


@contextmanager
def use_crop_db(db):
    token = _crop_db.set(db)
    try:
        yield
    finally:
        _crop_db.reset(token)


@contextmanager
def capture_crops():
    """Keep generated crop PNGs in memory for a stateless API response."""
    captured: dict[str, bytes] = {}
    token = _captured_crops.set(captured)
    try:
        yield captured
    finally:
        _captured_crops.reset(token)


def _content_name(payload: bytes, suffix: str) -> str:
    """Filename derived from content, so identical bytes land on one path.

    Previously every upload got a fresh uuid4, so re-uploading the same photo
    stored it again and re-ran the model. User 6 had one original on disk three
    times (7MB each) and 7 byte-identical duplicate item pairs.
    """
    return f"{hashlib.sha256(payload).hexdigest()[:32]}{suffix}"


def get_user_storage_dir(user_id: int, category_folder: str = "originals") -> Path:
    base = Path(settings.STORAGE_ROOT).resolve()
    user_dir = base / "users" / str(user_id) / category_folder
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def validate_image(raw: bytes, content_type: str) -> Image.Image:
    """Validate an uploaded image and return its EXIF-corrected RGB pixels."""
    # 1. Size check
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(raw) > max_bytes:
        raise HTTPException(413, f"Image must be under {settings.MAX_UPLOAD_MB}MB")

    # 2. Content-Type declared check
    allowed_types = [t.strip() for t in settings.ALLOWED_IMAGE_TYPES.split(",")]
    if content_type not in allowed_types:
        raise HTTPException(415, "Only JPEG, PNG and WebP images are accepted")

    # 3. Decode & verify (Content-Type header can be spoofed)
    try:
        img_temp = Image.open(io.BytesIO(raw))
        img_temp.verify()
        img = Image.open(io.BytesIO(raw))
    except Exception:
        raise HTTPException(400, "Invalid image file")

    # 4. Decompression bomb check
    if img.width * img.height > 50_000_000:
        raise HTTPException(400, "Image resolution is too large")

    # 5. EXIF rotation + strip location metadata via RGB re-encoding
    return ImageOps.exif_transpose(img).convert("RGB")


def validate_and_store_original(raw: bytes, content_type: str, user_id: int) -> tuple[str, int, Image.Image]:
    img_clean = validate_image(raw, content_type)

    # 6. Content-addressed filename (server-generated, never client input).
    # Hashes the normalised JPEG we are about to write, not the raw upload, so
    # the same photo re-encoded or re-wrapped still lands on one path.
    buf = io.BytesIO()
    img_clean.save(buf, "JPEG", quality=88)
    payload = buf.getvalue()

    stored_name = _content_name(payload, ".jpg")
    dest_dir = get_user_storage_dir(user_id, "originals")
    dest_path = dest_dir / stored_name

    # Path traversal check
    user_base = (Path(settings.STORAGE_ROOT).resolve() / "users" / str(user_id)).resolve()
    if not dest_path.resolve().is_relative_to(user_base):
        raise HTTPException(400, "Bad storage path")

    # Nothing reads originals back; they are kept only so the user has their own
    # photos on the laptop. Cloud container disks are ephemeral, so writing them
    # there costs disk and buys nothing. The uploads table carries the same hash,
    # so it, not the filesystem, answers "seen this photo before".
    if not settings.CLOUD_MODE and not dest_path.exists():
        dest_path.write_bytes(payload)

    return stored_name, len(payload), img_clean


def save_garment_crop(crop_img: Image.Image, user_id: int, db=None) -> tuple[str, int]:
    # Cap the longest side. Cutouts were being written at source resolution,
    # which produced 18.5MB PNGs for a single wardrobe item.
    if max(crop_img.size) > settings.OUTPUT_MAX_SIDE:
        scale = settings.OUTPUT_MAX_SIDE / max(crop_img.size)
        crop_img = crop_img.resize(
            (max(1, round(crop_img.width * scale)), max(1, round(crop_img.height * scale))),
            Image.LANCZOS,
        )

    buf = io.BytesIO()
    crop_img.save(buf, "PNG", optimize=True)
    payload = buf.getvalue()

    stored_name = _content_name(payload, ".png")
    captured = _captured_crops.get()
    if captured is not None:
        captured[stored_name] = payload
        return stored_name, len(payload)

    db = db or _crop_db.get()
    return stored_name, crops.put(db, user_id, stored_name, payload)


# Crops are written during segmentation, before the user accepts them on the
# Review screen. An abandoned review therefore leaves 1-2MB on disk forever.
# shortcut: swept opportunistically on the next upload rather than tracked per
# session; raise ORPHAN_CROP_AGE if a review can ever take longer than an hour.
ORPHAN_CROP_AGE = 3600


def sweep_orphan_crops(user_id: int, keep: set[str], db=None) -> int:
    """Remove item crops older than an hour that no item row points at."""
    if _captured_crops.get() is not None:
        return 0
    freed = 0
    db = db or _crop_db.get()
    for name, size in crops.old_names(db, user_id, ORPHAN_CROP_AGE).items():
        if name not in keep and not (name.startswith("flat-") and name[5:] in keep):
            crops.delete(db, user_id, name)
            freed += size
    return freed
