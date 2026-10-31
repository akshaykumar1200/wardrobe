---
id: flat-view-api
files: [wardrobe/backend/flatten.py, wardrobe/backend/config.py, wardrobe/backend/routers/items.py, wardrobe/backend/storage.py, wardrobe/tests/test_flatten.py]
test: cd wardrobe && venv\Scripts\python.exe -m pytest tests -q
effort: high
sandbox: full
timeout: 60
---
Add a **"flat view"** for tops: take the real pixels of a T-shirt from the
photo of someone wearing it and move them into a flat, front-on, symmetric
T-shirt shape, like a product photo. Real pixels are moved, never redrawn, so
seams, prints and texture survive. Areas the photo never showed (under the
arms, below the frame) are filled with the LaMa inpainting model.

A hand-placed-landmark prototype of exactly this was validated: 89.5% of the
flat shirt came from real pixels and the seams survived. Your job is to make
it **automatic** and serve it from the API. It runs on the laptop backend.

Read `backend/segmenter.py` (`_predict`, `_resize_to`, `PERSON_PART_IDS`),
`backend/crops.py`, `backend/storage.py`, `backend/routers/items.py` and
`backend/routers/images.py` first.

## 1. `backend/flatten.py` (new)

Public entry point:
`def flatten_top(photo: PIL.Image.Image) -> tuple[bytes, dict]` returning a
transparent-background RGBA PNG and a small info dict (fraction filled from
real pixels, whether the hem was extended, seconds taken). It raises
`NotSuitable(reason)` (define it here) when the photo cannot give a sensible
result. Refusing is better than returning garbage.

### a. Labels
Cap the photo with `segmenter._resize_to(img, settings.WORK_SIDE)` and get
probabilities with `segmenter._predict(img)` (shape classes x H x W), then
`argmax` for a label map. **Reuse the already-loaded model in `segmenter`; do
not load a second copy.** Take ids from `segmenter.model.config.id2label` by
name, never hard-coded numbers.

- Garment = largest connected component of **"Upper-clothes" OR "Dress"**,
  holes filled. Both labels on purpose: in waist-up photos this model labels a
  long T-shirt as "Dress" (seen on real photos: 0% Upper-clothes, 16% Dress).
- Arms = "Left-arm" OR "Right-arm". Neck reference = "Face" OR "Hair".

### b. Landmarks (worn, roughly front-facing top)
All in image pixels, x right, y down. Let `cx` = garment centroid x, garment
bbox width `w`, height `h`. Each fraction below is a named module constant.

- **neck L / R**: highest point (min y) of the garment's top edge, searched in
  `[cx - 0.3w, cx)` and `(cx, cx + 0.3w]`.
- **collar centre**: lowest point of the top edge between neck L and neck R
  (the dip of the neckline).
- **sleeve cuff outer / inner, each side**: the garment pixels touching the arm
  mask (dilate arms by 2 px) on that side of `cx`; outer = the one farthest
  from `cx`, inner = the one nearest `cx`. The inner cuff point doubles as the
  **armpit**. If a side has no arm contact, fall back to the garment's
  lateral-most point on that side for outer, and the point on the garment's
  side edge 0.25h below the neck for inner.
- **shoulder, each side**: the top-edge point at
  `x = neck.x + 0.55 * (cuff_outer.x - neck.x)`.
- **hem L / R / centre**: the bottom edge. L/R = outermost columns whose bottom
  y is within 3% of h of the lowest bottom y; centre = bottom y at `cx`.
  **If the garment touches the bottom of the frame**, the real hem is below
  the photo: move all three hem points down by `HEM_EXTEND = 0.07 * h` and
  report `hem_extended: True`.
- **body side, each side**: halfway in y between armpit and hem, the garment's
  outermost pixel in that row on that side.
- **chest / stomach centre**: on the collar-centre-to-hem-centre line at 30%
  and 70%.

**Sanity checks: raise `NotSuitable` with a plain-English reason** when: no
garment found; garment smaller than 2% of the frame; neck points not found;
cuff outer not further from `cx` than the shoulder on either side; hem not
below both armpits; height/width ratio outside 0.6 to 2.5.

### c. Flat target shape (built from the shirt's own proportions)
Measure from the landmarks: neck width, collar depth, shoulder half-width and
drop, sleeve length (shoulder to cuff outer, averaged over both sides), cuff
width (cuff outer to inner), body width (`max` of hem width and side-to-side
width, because arms hide the sides), body length (collar centre to hem
centre). Build the **same landmarks in a canonical layout**: symmetric about
the canvas centre, neck at the top, sleeves pointing outwards and down at
`SLEEVE_ANGLE_DEG = 35` below horizontal, then scale so the whole garment fits
a `CANVAS = 768` px square with a 6% margin.

The target silhouette is the polygon through the outline landmarks in order:
neck L, shoulder L, cuff outer L, cuff inner L, body side L, hem L, hem
centre, hem R, body side R, cuff inner R, cuff outer R, shoulder R, neck R,
collar centre. Rasterise it with PIL, then soften the corners slightly (a
small blur and re-threshold).

### d. Warp
Fit `scipy.interpolate.RBFInterpolator(target_pts, source_pts,
kernel="thin_plate_spline", smoothing=1.0)` on every landmark pair (outline
plus the two centre points). Map every target-silhouette pixel to the source
and sample the photo bilinearly (`scipy.ndimage.map_coordinates`). A target
pixel is **real** when its source position lands inside the garment mask
eroded by 3 px and outside the arm mask; otherwise it is a **hole**.

### e. Even out broad lighting
On the real pixels only, in Lab: divide L by a normalised Gaussian blur of L
(blur of valid pixels divided by blur of the valid mask), sigma
`LIGHT_SIGMA = 0.045 * CANVAS`, then rescale to the median L of the real
pixels. This removes broad body shading and keeps seams and texture. Add a
one-line comment that it cannot remove sharp cast shadows.

### f. Fill holes with LaMa
Load `settings.LAMA_MODEL_PATH` with `torch.jit.load(..., map_location="cpu")`
**lazily, once**, behind a lock, cached in a module global. It is verified to
load in this venv's torch 2.0.1. Inputs are float tensors in 0..1: image
`(1,3,H,W)` RGB, mask `(1,1,H,W)` with 1 = fill; the output is `(1,3,H,W)`
in 0..1. Pad H and W up to a multiple of 8 and crop back.

- To save time, run LaMa only on the bounding box of the dilated hole mask
  plus a 64 px margin, and paste the result back **only into hole pixels**.
  Real pixels must stay untouched.
- Before LaMa, paint everything **outside** the silhouette with the median
  colour of the real pixels. In the prototype a white background made LaMa
  fill the hem strip with whitish colour.
- If the model file is missing, raise a dedicated `ModelMissing` error.

### g. Output
RGBA PNG on a transparent background: alpha = the silhouette, feathered by
about 1.5 px. Info dict keys: `real_fraction`, `hem_extended`, `seconds`.

## 2. `backend/config.py`
Add `LAMA_MODEL_PATH: str` defaulting to
`str(Path.home() / ".cache" / "torch" / "hub" / "checkpoints" / "big-lama.pt")`.

## 3. `POST /api/items/{item_id}/flat` in `backend/routers/items.py`
- Must belong to the signed-in user, else **404** (same pattern as the other
  item routes).
- Not `topwear` → **400** "Flat view works for tops only for now."
- The original photo comes from the item's upload: `Upload.stored_name` under
  `storage.get_user_storage_dir(user.id, "originals")`. If there is no upload
  or the file is not on this server's disk → **400** "The original photo for
  this item isn't stored on this server." (Cloud mode never keeps originals.)
- `NotSuitable` → **422** with its reason. `ModelMissing` → **503** "Flat view
  isn't available on this server."
- Apply EXIF orientation, then run `flatten_top` in the threadpool
  (`run_in_threadpool`, as `uploads.py` does).
- Store the PNG as a crop named **`flat-` + item.stored_name**. `crops.put`
  silently keeps an existing file of the same name, so **delete the old flat
  crop first**, then put, then commit. Regenerating must replace the image.
- Respond `{"stored_name": "flat-...", "real_fraction": ..., "hem_extended":
  ..., "seconds": ...}`. The existing `GET /api/images/item/{stored_name}`
  serves it with its per-user ownership check; do not add an image route.
- Rate-limit with the existing `limiter` at `6/minute`, adding the
  `request: Request` parameter slowapi requires.

**Item delete** (`delete_item`): when the item's crop is deleted (the "last
reference" branch), also delete `flat-` + its stored_name.

## 4. `backend/storage.py`
`sweep_orphan_crops` deletes every crop older than an hour that is not in
`keep`, which would delete every flat view an hour after it was made. Fix it
**there, once**: a name `flat-X` counts as kept when `X` is in `keep`. Do not
change the caller in `uploads.py`.

## 5. `tests/test_flatten.py` (new)
Follow the fixtures in the existing tests. Use **synthetic label maps and
images** (a T-shirt polygon labelled as the upper-clothes id, two arm
rectangles under the sleeves, a face blob above). **Never load the real
segmentation model or LaMa in tests**: monkeypatch `_predict` and the LaMa
call. Cover:
- landmarks: neck points near the top, cuff outer further out than the
  shoulders, armpits below the shoulders, hem lowest
- a garment touching the frame bottom → `hem_extended` is true
- a photo with no garment → `NotSuitable`
- warp end to end with LaMa monkeypatched to paint a fixed colour: output is
  RGBA; real pixels keep their source colours (draw a distinctive stripe on
  the synthetic shirt and assert it appears in the output); hole pixels get
  the fill colour
- endpoint: non-topwear → 400; another user's item → 404; missing original →
  400; success stores `flat-<name>`, which the images route then serves;
  calling it twice replaces the image (assert the bytes change when the fake
  flatten returns different bytes)
- `sweep_orphan_crops` keeps `flat-X` when `X` is kept, removes it when not
- deleting an item removes its flat crop

## Done when
`cd wardrobe && venv\Scripts\python.exe -m pytest tests -q` passes all 52
existing tests plus the new ones, none skipped.

## Do not
- Do not add any dependency. numpy, scipy, PIL and torch are installed.
  OpenCV is **not** installed in this venv: do the Lab conversion with your
  own small numpy sRGB/Lab functions.
- Do not load a second segmentation model, and do not import from `iopaint`.
- Do not change the upload flow, the review flow, models or the schema.
- Do not touch `frontend/` or `../android_app/`.
