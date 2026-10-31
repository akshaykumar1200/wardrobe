---
id: cutout-api
files: [wardrobe/backend/routers/cutout.py, wardrobe/backend/main.py, wardrobe/backend/storage.py, wardrobe/backend/config.py, wardrobe/tests/test_cutout.py]
test: cd wardrobe && venv\Scripts\python.exe -m pytest tests -q
effort: high
sandbox: full
timeout: 45
---
A **separate website** (built with Lovable, its own Supabase project and its
own users) needs real garment cut-outs. This FastAPI backend already makes
them with segformer + BiRefNet in `segmenter.extract_garments`. Expose that as
a **stateless, server-to-server cut-out service**: the Lovable server sends a
photo plus a shared secret, and gets back each garment as a transparent PNG
with its category and colour. **Nothing may be stored** in this backend's
database or on disk for these requests; they are not this app's users.

Read `backend/segmenter.py` (`extract_garments` and what it returns),
`backend/storage.py` (`save_garment_crop`, `_crop_db`, `use_crop_db`),
`backend/routers/uploads.py` (how an upload is validated and run in the
threadpool), `backend/auth.py` (`limiter`) and `backend/config.py` first.

## 1. `backend/storage.py`: a capture mode for crops
`extract_garments` saves each crop through `save_garment_crop`, which writes to
the crop store. Add a capture mode beside the existing `_crop_db` ContextVar:

- a `ContextVar` holding a dict, plus a context manager
  `capture_crops()` that sets it to a fresh dict, yields it, and resets it
- in `save_garment_crop`: when capture mode is active, build the PNG exactly as
  now (same resize cap, same encoding, same content-hash name), put
  `name -> png bytes` into the dict, and **return without touching the
  database or disk**
- any other cleanup `extract_garments` does through storage (for example a
  sweep or orphan cleanup) must also be a no-op in capture mode; check every
  storage call it makes

Outside capture mode, behaviour must stay byte-for-byte identical. The
existing tests prove that.

## 2. `backend/config.py`
Add `CUTOUT_API_KEY: str = ""`. Empty means the service is switched off.

## 3. `backend/routers/cutout.py` (new), mounted in `main.py`
`POST /api/cutout`, multipart form with one file field `image`.

- **Auth:** header `X-Cutout-Key`. If `settings.CUTOUT_API_KEY` is empty →
  **503** "Cut-out service is not configured." If the header is missing or
  wrong → **401**. Compare with `secrets.compare_digest`. This route uses
  **no** user session and must not accept cookies or bearer tokens in place of
  the key.
- **Rate limit:** the existing `limiter`, `20/minute`.
- **Validation:** the same size and type limits uploads use (reuse the
  existing validation code, not a copy), but **do not write the original to
  disk**. If the existing helper both validates and stores, split the
  validation into its own function and make the existing helper call it, so
  uploads keep working exactly as before.
- **Work:** apply EXIF orientation, then run `extract_garments` inside
  `capture_crops()` in the threadpool (`run_in_threadpool`, as uploads does).
  Pass `user_id=0`; it is only used to build storage paths, which capture mode
  never uses.
- **Response 200:**
  ```
  {"items": [{"name": str, "category": str, "color": str, "confidence": float|null,
              "width": int, "height": int, "png_base64": str}],
   "notice": str|null, "seconds": float}
  ```
  `png_base64` is the captured crop for that item's `stored_name`; do not
  return `stored_name`.
- Never log the key or the image bytes.

## 4. `tests/test_cutout.py` (new)
Follow the fixtures and style of the existing tests. **Monkeypatch
`extract_garments`** (no real model) with a fake that calls
`save_garment_crop` on two small RGBA images and returns two items, exactly as
the real one does. Cover:
- key not configured → 503; missing key → 401; wrong key → 401
- a session cookie or bearer token **without** the key → 401
- valid key → 200 with 2 items whose `png_base64` decodes to RGBA PNGs of the
  right size, and with no `stored_name`
- **nothing persisted:** after a successful call, the crop store has no new
  blobs and no new files under the storage root
- outside capture mode `save_garment_crop` still stores, as before
- an oversized or non-image upload is rejected with the same status the
  uploads route uses

## Done when
`cd wardrobe && venv\Scripts\python.exe -m pytest tests -q` passes, with no
new failures. The 2 failing tests in `tests/test_flatten.py` are known and are
not yours to fix; don't touch them.

## Do not
- Do not change `segmenter.py`'s extraction logic, models or thresholds.
- Do not touch `flatten.py`, `routers/items.py`, the frontend or `../android_app/`.
- Do not add a dependency.
- Do not write a key into any file; tests set `settings.CUTOUT_API_KEY` with monkeypatch.
