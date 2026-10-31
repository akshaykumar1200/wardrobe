import asyncio
import base64
import hashlib
import io
import secrets
import time

from fastapi import APIRouter, File, Header, HTTPException, Request, UploadFile
from PIL import Image
from starlette.concurrency import run_in_threadpool

from backend.auth import limiter
from backend.config import settings
from backend.segmenter import extract_garments
from backend.storage import capture_crops, validate_image

router = APIRouter(prefix="/api/cutout", tags=["cutout"])

# The caller may send the same photo several times at once (one call per piece it
# found); each run takes ~30 s of CPU, so identical photos share one run and its
# result is reused for a short while. shortcut: per-process, fine for one laptop worker.
REUSE_SECONDS = 300
_jobs: dict[str, tuple[float, asyncio.Task]] = {}


@router.post("")
@limiter.limit("20/minute")
async def cutout_photo(
    request: Request,
    image: UploadFile = File(...),
    x_cutout_key: str | None = Header(None, alias="X-Cutout-Key"),
):
    if not settings.CUTOUT_API_KEY:
        raise HTTPException(503, "Cut-out service is not configured.")
    if x_cutout_key is None or not secrets.compare_digest(
        x_cutout_key.encode("utf-8"), settings.CUTOUT_API_KEY.encode("utf-8")
    ):
        raise HTTPException(401, "Invalid cut-out key")

    raw = await image.read()
    if not raw:
        raise HTTPException(400, "Empty upload file")
    img_clean = validate_image(raw, image.content_type or "image/jpeg")

    now = time.monotonic()
    for key, (started, job) in list(_jobs.items()):
        if job.done() and now - started > REUSE_SECONDS:
            del _jobs[key]
    digest = hashlib.sha256(raw).hexdigest()
    if digest not in _jobs:
        _jobs[digest] = (now, asyncio.ensure_future(_cut_out(img_clean)))
    started, job = _jobs[digest]
    try:
        # shield: one caller hanging up must not cancel the run the others wait on
        return await asyncio.shield(job)
    except Exception:
        _jobs.pop(digest, None)   # never reuse a failure
        raise


async def _cut_out(img_clean: Image.Image) -> dict:
    started = time.monotonic()
    with capture_crops() as captured:
        result = await run_in_threadpool(extract_garments, img_clean, 0, complete=True)
    seconds = time.monotonic() - started

    items = []
    for item in result["items"]:
        png = captured[item["stored_name"]]
        with Image.open(io.BytesIO(png)) as crop:
            width, height = crop.size
        items.append({
            "name": item["name"],
            "category": item["category"],
            "color": item["color"],
            "confidence": item.get("confidence"),
            "width": width,
            "height": height,
            "png_base64": base64.b64encode(png).decode("ascii"),
        })

    # Sizes and labels only, never the image or the key: shows what each caller's photo yielded.
    print(f"cutout {img_clean.size[0]}x{img_clean.size[1]} -> "
          f"{[(i['name'], i['width'], i['height'], r.get('filled')) for i, r in zip(items, result['items'])]} in {seconds:.1f}s"
          f"{' notice: ' + result['notice'] if result['notice'] else ''}", flush=True)
    return {"items": items, "notice": result["notice"], "seconds": seconds}
