import asyncio
import base64
import hashlib
import io
import secrets
import time

import numpy as np
from fastapi import APIRouter, File, Form, Header, HTTPException, Request, UploadFile
from PIL import Image
from starlette.concurrency import run_in_threadpool

from backend import flow_shot, product_shot
from backend.auth import limiter
from backend.config import settings
from backend.flatlay import generate_flatlay
from backend.matting import subject_matte
from backend.segmenter import extract_garments
from backend.storage import capture_crops, validate_image

router = APIRouter(prefix="/api/cutout", tags=["cutout"])

# The caller may send the same photo several times at once (one call per piece it
# found); each run takes ~30 s of CPU, so identical photos share one run and its
# result is reused for a short while. shortcut: per-process, fine for one laptop worker.
REUSE_SECONDS = 300
_jobs: dict[str, tuple[float, asyncio.Task]] = {}


def _check_cutout_key(x_cutout_key: str | None) -> None:
    if not settings.CUTOUT_API_KEY:
        raise HTTPException(503, "Cut-out service is not configured.")
    if x_cutout_key is None or not secrets.compare_digest(
        x_cutout_key.encode("utf-8"), settings.CUTOUT_API_KEY.encode("utf-8")
    ):
        raise HTTPException(401, "Invalid cut-out key")


@router.post("")
@limiter.limit("20/minute")
async def cutout_photo(
    request: Request,
    image: UploadFile = File(...),
    x_cutout_key: str | None = Header(None, alias="X-Cutout-Key"),
):
    _check_cutout_key(x_cutout_key)

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


@router.post("/mask")
@limiter.limit("20/minute")
async def cutout_mask(
    request: Request,
    image: UploadFile = File(...),
    x_cutout_key: str | None = Header(None, alias="X-Cutout-Key"),
):
    _check_cutout_key(x_cutout_key)

    raw = await image.read()
    if not raw:
        raise HTTPException(400, "Empty upload file")
    img_clean = validate_image(raw, image.content_type or "image/jpeg")
    matte = await run_in_threadpool(subject_matte, img_clean)
    if matte is None:
        raise HTTPException(503, "Background removal is not available.")

    alpha = np.asarray(matte)
    ys, xs = np.where(alpha > 0.05)
    if len(xs) == 0:
        raise HTTPException(422, "No subject found.")

    width, height = img_clean.size
    pad = int(np.ceil(0.02 * max(width, height)))
    x0 = max(0, int(xs.min()) - pad)
    y0 = max(0, int(ys.min()) - pad)
    x1 = min(width, int(xs.max()) + 1 + pad)
    y1 = min(height, int(ys.max()) + 1 + pad)
    mask = Image.fromarray(np.rint(np.clip(alpha[y0:y1, x0:x1], 0, 1) * 255).astype(np.uint8), mode="L")
    buf = io.BytesIO()
    mask.save(buf, format="PNG")
    return {
        "width": width,
        "height": height,
        "crop_box": [x0, y0, x1, y1],
        "mask_png_base64": base64.b64encode(buf.getvalue()).decode("ascii"),
    }


@router.post("/flatlay")
@limiter.limit("20/minute")
async def start_flatlay(
    request: Request,
    image: UploadFile = File(...),
    name: str = Form("garment"),
    x_cutout_key: str | None = Header(None, alias="X-Cutout-Key"),
):
    """Starts Flow's clean picture for a cut-out the caller already has (a re-uploaded photo's saved piece)."""
    _check_cutout_key(x_cutout_key)
    raw = await image.read()
    if not raw:
        raise HTTPException(400, "Empty upload file")
    validate_image(raw, image.content_type or "image/png")   # size and type checks only:
    shot_id = flow_shot.start(raw, name[:60])                # it returns RGB, and Flow needs the transparency
    if shot_id is None:
        raise HTTPException(503, "Clean pictures are not set up on this laptop.")
    return {"flatlay_id": shot_id}


@router.get("/flatlay/{shot_id}")
async def cutout_flatlay(shot_id: str, x_cutout_key: str | None = Header(None, alias="X-Cutout-Key")):
    """Flow's clean picture for one item of an earlier cut-out: pending, ready (with the PNG), or failed."""
    _check_cutout_key(x_cutout_key)
    state, png = flow_shot.status(shot_id)
    if state == "unknown":
        raise HTTPException(404, "No such picture (it may have expired or the service restarted).")
    body = {"status": state}
    if png:
        body["png_base64"] = base64.b64encode(png).decode("ascii")
    return body


async def _cut_out(img_clean: Image.Image) -> dict:
    started = time.monotonic()
    shot = product_shot.start(img_clean)   # draws the top on the GPU while the CPU cuts out
    try:
        with capture_crops() as captured:
            result = await run_in_threadpool(extract_garments, img_clean, 0, complete=True)
        # shortcut: TryOffDiff draws one upper garment, so with two tops (shirt + jacket)
        # there is no telling which it drew; both keep their cut-outs.
        tops = [i for i in result["items"] if i["category"] == "topwear"]
        if shot and len(tops) == 1:
            drawn = await run_in_threadpool(shot.result)
            if drawn is not None:
                with Image.open(io.BytesIO(captured[tops[0]["stored_name"]])) as real:
                    product = await run_in_threadpool(product_shot.recolour, drawn, real)
                if product is not None:
                    buf = io.BytesIO()
                    product.save(buf, format="PNG")
                    captured[tops[0]["stored_name"]] = buf.getvalue()
                    tops[0]["drawn"] = True
    finally:
        if shot:
            shot.close()

    async def _process_item(item):
        png = captured[item["stored_name"]]
        flatlay_bytes = None
        # Apply flat-lay generation to apparel (tops, bottomwear, dresses, etc.)
        # A top TryOffDiff already drew is not sent to Gemini as well.
        if settings.FLATLAY_ENABLED and not item.get("drawn") and item.get("category") in ("topwear", "bottomwear", "other"):
            flatlay_bytes = await generate_flatlay(png, item["name"], item["color"])

        final_png = flatlay_bytes if flatlay_bytes is not None else png
        with Image.open(io.BytesIO(final_png)) as crop:
            width, height = crop.size

        # Flow takes minutes, so the website gets the cut-out now and fetches Flow's picture by this id.
        shot_id = None
        if flatlay_bytes is None and not item.get("drawn") and item.get("category") in ("topwear", "bottomwear", "other"):
            shot_id = flow_shot.start(png, item["name"])

        return {
            "flatlay_id": shot_id,
            "name": item["name"],
            "category": item["category"],
            "color": item["color"],
            "confidence": item.get("confidence"),
            "width": width,
            "height": height,
            "png_base64": base64.b64encode(final_png).decode("ascii"),
            "is_flatlay": flatlay_bytes is not None or bool(item.get("drawn")),
        }

    items = await asyncio.gather(*[_process_item(item) for item in result["items"]])
    seconds = time.monotonic() - started

    # Sizes and labels only, never the image or the key: shows what each caller's photo yielded.
    print(f"cutout {img_clean.size[0]}x{img_clean.size[1]} -> "
          f"{[(i['name'], i['width'], i['height'], r.get('filled'), 'drawn' if r.get('drawn') else 'flat-lay' if i['is_flatlay'] else 'cut-out') for i, r in zip(items, result['items'])]} in {seconds:.1f}s"
          f"{' notice: ' + result['notice'] if result['notice'] else ''}", flush=True)
    return {"items": items, "notice": result["notice"], "seconds": seconds}
