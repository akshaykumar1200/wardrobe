import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from scipy import ndimage
from transformers import SegformerImageProcessor, AutoModelForSemanticSegmentation

from backend import matting
from backend.config import settings
from backend.storage import save_garment_crop

torch.set_num_threads(settings.TORCH_THREADS)

# Model loaded once at startup
processor = SegformerImageProcessor.from_pretrained(settings.MODEL_ID)
model = AutoModelForSemanticSegmentation.from_pretrained(settings.MODEL_ID)
model.eval()

# One entry per garment we emit. `ids` groups the model's classes so that a
# left shoe and a right shoe become a single "Shoes" item instead of two
# half-pairs. `parts` is how many disconnected blobs are legitimate.
GARMENT_GROUPS = [
    {"ids": (4,),     "category": "topwear",     "name": "Top",        "parts": 1},
    {"ids": (5,),     "category": "bottomwear",  "name": "Skirt",      "parts": 1},
    {"ids": (6,),     "category": "bottomwear",  "name": "Trousers",   "parts": 2},
    {"ids": (7,),     "category": "other",       "name": "Dress",      "parts": 1},
    {"ids": (9, 10),  "category": "shoes",       "name": "Shoes",      "parts": 2},
    {"ids": (1,),     "category": "accessories", "name": "Hat",        "parts": 1},
    {"ids": (3,),     "category": "accessories", "name": "Sunglasses", "parts": 2},
    {"ids": (16,),    "category": "accessories", "name": "Bag",        "parts": 1},
]

# All thresholds are fractions of the frame, not absolute pixel counts. The old
# absolute MIN_PIXELS=1500 was ~0.01% of a 12MP phone photo, so it rejected
# nothing and 99x43px specks were being stored as garments.
MIN_AREA_FRAC = 0.004   # below this it is a speck, not a garment
MAX_AREA_FRAC = 0.60    # above this the mask has swallowed the background
MIN_FILL_RATIO = 0.15   # mask area vs its own bbox; scattered masks are leaks
MIN_CONFIDENCE = 0.55   # mean softmax prob inside the mask
PART_MIN_FRAC = 0.12    # a secondary blob must be >=12% of the largest to count

# Colour refinement. Only groups the model is unsure about get refined; Tops and
# Trousers come back at 0.97-0.99 and are already clean, so touching them could
# only make them worse.
REFINE_BELOW = 0.85     # refine a group whose mean certainty is under this
REFINE_BAND_FRAC = 0.011  # uncertain band width, as a fraction of the long side
# Deliberately close to 1.0. The model is not merely hesitant about the sole, it
# is confidently wrong: a third of those pixels score above 0.90, so a gate down
# there discarded most of what the refinement exists to recover. Only the truly
# saturated pixels -- the wall and open floor at 0.997+ -- are worth excluding.
REFINE_BG_GATE = 0.995
REFINE_FG_CLUSTERS = 3    # a shoe is white upper + grey shadow + dark mesh
REFINE_BG_CLUSTERS = 5    # ground, wall, painted stripe, trousers, foliage
MIN_ADDED_COMPONENT = 60  # absorbed blobs smaller than this are ground speckle

BACKGROUND_ID = 0

# Classes that can only exist if a real person is in the frame. This model
# segments people, so a flat-lay of a garment on a bed has no valid answer -- it
# returned "upper-clothes" for a pair of sneakers at 0.66 and filed them as a
# Top. Measured across this user's photos: real shots score 0.87-0.94 here, the
# flat-lay scored 0.36, so the gap is wide enough to act on.
PERSON_PART_IDS = (2, 11, 12, 13, 14, 15)   # hair, face, legs, arms
MIN_PERSON_FRAC = 0.005
MIN_PERSON_CONF = 0.65

# Flat-lay fallback, used only when no person is present.
FLATLAY_BORDER = 0.06     # frame edge sampled as "this is the surface"
FLATLAY_CLUSTERS = 4
FLATLAY_MARGIN = 1.25     # multiplier on the Otsu split, for the strong seed
FLATLAY_WEAK_RATIO = 0.85  # doubtful pixels are kept only if joined to a seed
FLATLAY_MIN_THRESHOLD = 6.0
FLATLAY_REFINE_BAND_FRAC = 0.030   # local repair band, wider than the worn path
# Veto for the local repair, as a fraction of the weak hysteresis threshold.
# Must stay below 1.0: the blob is already everything above weak_t, so a veto at
# weak_t itself leaves ~500 eligible pixels and cancels the repair entirely.
FLATLAY_ELIGIBLE_RATIO = 0.6
FLATLAY_MAX_AREA = 0.75   # above this the "subject" is really the surface

# Completing a worn garment: paint in what a hand, arm, hair or bag hid.
OCCLUDER_IDS = (2, 14, 15, 16, 17)   # hair, arms (hands are part of them), bag, scarf
COMPLETE_RADIUS_FRAC = 0.03   # closes notches up to ~6% of the long side wide
COMPLETE_MAX_FRAC = 0.25      # hiding more than this means guessing the shape, not repairing it
COMPLETE_MIN_FRAC = 0.01      # less is invisible, and LaMa still costs ~20 s on CPU
LAMA_MAX_SIDE = 1024          # LaMa on CPU slows sharply past this


def _resize_to(img: Image.Image, max_side: int) -> Image.Image:
    if max(img.size) <= max_side:
        return img
    scale = max_side / max(img.size)
    new_size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
    return img.resize(new_size, Image.LANCZOS)


def _predict(img: Image.Image) -> np.ndarray:
    """Per-class probabilities at `img` resolution, shape (classes, H, W).

    `img` is already capped to WORK_SIDE. Upsampling logits straight to a 12MP
    original allocated ~880MB per tensor, so the whole mask stage now runs at a
    bounded working resolution and the crop is taken from the same raster.
    """
    small = _resize_to(img, settings.INFERENCE_SIDE)

    inputs = processor(images=small, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)

    upsampled = nn.functional.interpolate(
        outputs.logits.cpu(),
        size=(img.height, img.width),
        mode="bilinear",
        align_corners=False,
    )
    return upsampled.softmax(dim=1)[0].numpy()


def _group_mask(probs: np.ndarray, ids: tuple) -> np.ndarray:
    """Decide the group against the rest, rather than grouping after argmax.

    Left-shoe and right-shoe are the same garment to us, but as separate classes
    they split their probability mass: a sole pixel at 0.30 left + 0.30 right
    loses to 0.35 background even though it is 0.60 shoe. Summing the group
    first lets them vote together.
    """
    inside = probs[list(ids)].sum(axis=0)
    outside = np.delete(probs, list(ids), axis=0).max(axis=0)
    return inside > outside


def _refine_mask(mask: np.ndarray, rgb: np.ndarray, probs: np.ndarray) -> np.ndarray:
    """Grow a low-confidence mask into pixels that look like the garment.

    The clothes model reliably labels a white shoe sole as floor: it is
    confident about the fabric upper and wrong about everything pale around it,
    and neither more resolution nor a zoomed second pass changes that. Colour
    does separate them, so the coarse mask seeds a foreground/background colour
    model and only the uncertain band around the boundary is re-decided.

    Only pixels the model called *background* are eligible. That is the mistake
    being corrected -- it labels the sole as floor -- so anything it assigned to
    another garment or to a body part is left alone. Without that restriction the
    trouser hem between the shoes gets swallowed too. The step is purely
    additive: it can grow an under-segmented mask, never shrink a good one.
    """
    labels = probs.argmax(axis=0)
    certainty = probs.max(axis=0)
    eligible = (labels == BACKGROUND_ID) & (certainty <= REFINE_BG_GATE)
    band_px = max(6, round(max(mask.shape) * REFINE_BAND_FRAC))
    return _colour_grow(mask, rgb, band_px, eligible)


def _colour_grow(mask: np.ndarray, rgb: np.ndarray, band_px: int,
                 eligible: np.ndarray | None = None) -> np.ndarray:
    """Grow `mask` into nearby pixels that look like its interior.

    Shared by both extraction paths. Fits colour models to the mask's core and
    to a ring of surrounding pixels, then re-decides only the band between them.
    `eligible` restricts which pixels may ever be claimed; the worn-garment path
    passes the model's background pixels, the flat-lay path passes nothing and
    lets colour decide alone.
    """
    core = ndimage.binary_erosion(mask, np.ones((7, 7)))
    if core.sum() < 200:
        return mask

    # A distance transform gives the same band as repeated dilation for a
    # fraction of the cost; dilating with a 37x37 kernel was adding ~7s a photo.
    dist = ndimage.distance_transform_edt(~mask)
    candidates = (dist > 0) & (dist <= band_px)
    if eligible is not None:
        candidates &= eligible
    reference = (dist > band_px) & (dist <= band_px + 12)

    if candidates.sum() < 50 or reference.sum() < 200:
        return mask

    # Several clusters a side, not one Gaussian each. Around a worn shoe the
    # surroundings are concrete, a painted stripe, a white balustrade and dark
    # trousers at once; a single Gaussian spanning all of that is so broad that
    # nothing looks strongly like background, and pale wall got absorbed as
    # shoe. Fitting them separately gives the wall a tight cluster of its own,
    # so it is confidently background while the sole is still recovered.
    px = rgb[candidates]
    fg_model = _fit_clusters(rgb[core], REFINE_FG_CLUSTERS)
    bg_model = _fit_clusters(rgb[reference], REFINE_BG_CLUSTERS)
    if not fg_model or not bg_model:
        return mask

    claim = _max_loglik(px, fg_model) > _max_loglik(px, bg_model)

    grown = np.zeros_like(mask)
    ys, xs = np.where(candidates)
    grown[ys[claim], xs[claim]] = True

    # Drop small specks of absorbed ground, but by area rather than by opening:
    # the recovered sole is a long *thin* strip, and a 3x3 opening erased it
    # along with the speckle. Judging whole components keeps the strip and still
    # removes the scattered dots.
    labelled, count = ndimage.label(grown)
    if count:
        sizes = ndimage.sum(grown, labelled, range(1, count + 1))
        keep = [i + 1 for i, s in enumerate(sizes) if s >= MIN_ADDED_COMPONENT]
        grown = np.isin(labelled, keep)

    return mask | grown


def _keep_components(mask: np.ndarray, max_parts: int) -> np.ndarray:
    """Keep the largest blob plus any comparable ones, up to max_parts.

    The old code kept only the single largest component, which is why a pair of
    shoes came back as one shoe and a shirt split by a crossed arm lost half of
    itself.
    """
    labelled, count = ndimage.label(mask)
    if count <= 1:
        return mask

    sizes = ndimage.sum(mask, labelled, range(1, count + 1))
    order = np.argsort(sizes)[::-1]
    biggest = sizes[order[0]]

    keep = [order[0] + 1]
    for idx in order[1:max_parts]:
        if sizes[idx] >= biggest * PART_MIN_FRAC:
            keep.append(idx + 1)

    return np.isin(labelled, keep)


def _clean_mask(mask: np.ndarray, max_parts: int) -> np.ndarray:
    """Close gaps, drop stray blobs, fill interior holes.

    Deliberately no binary_opening: it was punching thousands of transparent
    holes through solid garments (22,615px in one crop) and eroding laces and
    thin straps. Component filtering removes speckle without that damage.
    """
    mask = ndimage.binary_closing(mask, np.ones((5, 5)))
    mask = _keep_components(mask, max_parts)
    return ndimage.binary_fill_holes(mask)


def _feather_alpha(mask: np.ndarray, width: float) -> np.ndarray:
    """Soft alpha from a signed distance field.

    `(mask * 255)` gave alpha that was only ever 0 or 255 -- zero anti-aliased
    pixels on every crop -- which is what made the cutouts read as torn paper.
    The ramp is pushed slightly inside the boundary so the semi-transparent
    pixels sample garment colour rather than background, avoiding a colour fringe.
    """
    inside = ndimage.distance_transform_edt(mask)
    outside = ndimage.distance_transform_edt(~mask)
    signed = inside - outside
    alpha = np.clip(signed / width + 0.5 - 0.25, 0.0, 1.0)
    return (alpha * 255).astype(np.uint8)


def _dominant_color(rgb: np.ndarray, core: np.ndarray) -> str:
    """Modal colour on a coarse grid, not the mean.

    Averaging RGB over a floral shirt returns mud. Bucketing to 32-level bins
    and taking the most populated bucket returns a colour you would actually
    name.
    """
    pixels = rgb[core]
    if len(pixels) == 0:
        return "#7d8c71"

    buckets = (pixels // 32).astype(np.int32)
    keys = buckets[:, 0] * 64 + buckets[:, 1] * 8 + buckets[:, 2]
    winner = np.bincount(keys).argmax()
    chosen = pixels[keys == winner]

    r, g, b = np.median(chosen, axis=0).astype(int)
    return f"#{r:02x}{g:02x}{b:02x}"


def _reject(mask: np.ndarray, certainty: np.ndarray, frame_area: int) -> str | None:
    """Geometric + confidence sanity checks. Returns a reason, or None if OK."""
    area = int(mask.sum())
    if area < frame_area * MIN_AREA_FRAC:
        return "too_small"
    if area > frame_area * MAX_AREA_FRAC:
        return "covers_frame"

    ys, xs = np.where(mask)
    bbox_area = (ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1)
    if area / bbox_area < MIN_FILL_RATIO:
        return "scattered"

    if float(certainty[mask].mean()) < MIN_CONFIDENCE:
        return "low_confidence"

    return None


def _hidden_part(mask: np.ndarray, labels: np.ndarray, long_side: int) -> np.ndarray:
    """Occluder pixels lying where the garment's own outline would continue.

    A morphological closing bridges the notch a hand cuts into a hem; only the
    pixels the model calls a hand, arm, hair or bag are taken from it, so a real
    opening such as the neckline (neck skin is "Face") is never filled. Done with
    distance transforms because a 77px structuring element is far too slow.
    """
    r = max(2, round(long_side * COMPLETE_RADIUS_FRAC))
    dilated = ndimage.distance_transform_edt(~mask) <= r
    closed = ndimage.distance_transform_edt(dilated) > r
    return (closed | mask) & np.isin(labels, OCCLUDER_IDS)


def _fill_hidden(crop: Image.Image, hidden: np.ndarray) -> Image.Image:
    """Paint the hidden pixels of a crop with LaMa; every other pixel stays real."""
    from backend import flatten   # flatten imports this module, so import late

    holes = np.array(Image.fromarray(hidden).resize(crop.size, Image.NEAREST))
    out = np.array(crop)
    rgb = out[..., :3].copy()
    solid = (out[..., 3] > 128) & ~holes
    if not holes.any() or not solid.any():
        return crop
    # LaMa reads its context from around the hole; the background would bleed in.
    rgb[~solid & ~holes] = np.median(rgb[solid], axis=0).astype(np.uint8)

    scale = min(1.0, LAMA_MAX_SIDE / max(crop.size))
    if scale < 1.0:
        small = (max(1, round(crop.width * scale)), max(1, round(crop.height * scale)))
        small_rgb = np.array(Image.fromarray(rgb).resize(small, Image.LANCZOS))
        # Bilinear then >0 marks every small pixel that touches a hole.
        small_holes = np.array(Image.fromarray(holes.astype(np.uint8) * 255).resize(small, Image.BILINEAR)) > 0
        filled = flatten._lama_fill(small_rgb, small_holes)
        filled = np.array(Image.fromarray(filled).resize(crop.size, Image.BICUBIC))
    else:
        filled = flatten._lama_fill(rgb, holes)

    out[..., :3][holes] = filled[holes]
    return Image.fromarray(out, mode="RGBA")


def _compose_crop(source: Image.Image, alpha: np.ndarray, box: tuple) -> Image.Image:
    """Cut the garment out of `source` at full detail using a low-res alpha.

    The mask is computed at WORK_SIDE for speed and memory, but taking the
    pixels from the downscaled raster too would throw away fabric texture. The
    alpha is smooth by construction, so scaling it back up to the original crop
    is lossless in practice while the RGB stays sharp.
    """
    y0, y1, x0, x1 = box
    ah, aw = alpha.shape
    sx, sy = source.width / aw, source.height / ah

    ox0, oy0 = int(np.floor(x0 * sx)), int(np.floor(y0 * sy))
    ox1, oy1 = int(np.ceil((x1 + 1) * sx)), int(np.ceil((y1 + 1) * sy))
    ox1, oy1 = min(ox1, source.width), min(oy1, source.height)

    rgb_crop = source.crop((ox0, oy0, ox1, oy1))
    alpha_crop = Image.fromarray(alpha[y0:y1 + 1, x0:x1 + 1], mode="L")
    alpha_crop = alpha_crop.resize(rgb_crop.size, Image.BICUBIC)

    out = rgb_crop.convert("RGBA")
    out.putalpha(alpha_crop)
    return out


def _kmeans(x: np.ndarray, k: int, iters: int = 15) -> np.ndarray:
    rs = np.random.RandomState(0)
    centres = x[rs.choice(len(x), k, replace=False)].astype(np.float64)
    labels = np.zeros(len(x), int)
    for _ in range(iters):
        labels = ((x[:, None, :] - centres[None]) ** 2).sum(-1).argmin(1)
        for j in range(k):
            if (labels == j).any():
                centres[j] = x[labels == j].mean(0)
    return centres, labels


def _fit_clusters(points: np.ndarray, k: int) -> list[tuple]:
    """Fit k Gaussians to a colour sample; returns (mean, inv cov, logdet, log weight)."""
    if k <= 1 or len(points) < k * 20:
        groups = [points]
    else:
        _, labels = _kmeans(points, k)
        groups = [points[labels == j] for j in range(k)]

    model = []
    for g in groups:
        if len(g) < 20:
            continue
        cov = np.cov(g.T) + np.eye(3) * 25.0
        model.append((g.mean(axis=0), np.linalg.inv(cov),
                      float(np.log(np.linalg.det(cov))),
                      float(np.log(max(len(g) / len(points), 1e-6)))))
    return model


def _max_loglik(px: np.ndarray, model: list[tuple]) -> np.ndarray:
    """Best log-likelihood of each pixel under any component of the model."""
    best = np.full(len(px), -np.inf, np.float32)
    for mu, inv, logdet, logw in model:
        delta = px - mu
        ll = (-0.5 * np.einsum("ij,jk,ik->i", delta, inv, delta)
              - 0.5 * logdet + logw)
        best = np.maximum(best, ll.astype(np.float32))
    return best


def _otsu(v: np.ndarray, bins: int = 256) -> float:
    lo, hi = float(v.min()), float(np.percentile(v, 99.5))
    hist, edges = np.histogram(np.clip(v, lo, hi), bins=bins)
    p = hist.astype(float) / max(hist.sum(), 1)
    cum = np.cumsum(p)
    mean = np.cumsum(p * np.arange(bins))
    denom = cum * (1 - cum)
    denom[denom == 0] = 1e-12
    between = (mean[-1] * cum - mean) ** 2 / denom
    return float(edges[int(np.argmax(between))])


def _flatlay_mask(rgb: np.ndarray) -> np.ndarray | None:
    """Cut a garment out of a photo with no person in it.

    The clothes model is useless here -- it called a pair of sneakers on a bed
    "upper-clothes" at 0.66 -- so this ignores it entirely. A flat-lay is an
    object on a broadly uniform surface, and the surface is whatever fills the
    frame border, so the border seeds a background colour model and anything far
    from it in colour is the subject.
    """
    h, w = rgb.shape[:2]
    by, bx = max(1, int(h * FLATLAY_BORDER)), max(1, int(w * FLATLAY_BORDER))
    edge = np.zeros((h, w), bool)
    edge[:by, :] = edge[-by:, :] = True
    edge[:, :bx] = edge[:, -bx:] = True

    sample = rgb[edge][::7]
    if len(sample) < 200:
        return None

    # Several clusters, because a real surface has shading and folds; one
    # Gaussian over "green bed in sun + green bed in shadow" fits neither.
    centres, labels = _kmeans(sample, FLATLAY_CLUSTERS)

    flat = rgb.reshape(-1, 3)
    best = np.full(len(flat), np.inf, np.float32)
    for j, centre in enumerate(centres):
        pts = sample[labels == j]
        if len(pts) < 20:
            continue
        cov = np.cov(pts.T) + np.eye(3) * 30.0
        weight = max((labels == j).mean(), 1e-6)
        delta = flat - centre
        d = np.einsum("ij,jk,ik->i", delta, np.linalg.inv(cov), delta) - 2.0 * np.log(weight)
        best = np.minimum(best, d.astype(np.float32))
    dist = best.reshape(h, w)

    # Hysteresis rather than one cut. A single threshold high enough to reject
    # the surface also rejects the garment's own pale parts -- a cream midsole
    # scores about as far from a pale bed as the bed does -- and bit notches out
    # of the shoe. So: seed on pixels clearly not-surface, then grow into merely
    # doubtful ones, but only where they connect to a seed. Pale bed elsewhere
    # in the frame stays out because nothing anchors it.
    strong_t = max(FLATLAY_MIN_THRESHOLD, _otsu(dist) * FLATLAY_MARGIN)
    weak_t = strong_t * FLATLAY_WEAK_RATIO

    weak = ndimage.binary_closing(dist > weak_t, np.ones((9, 9)))
    strong = dist > strong_t

    labelled_w, n_w = ndimage.label(weak)
    if n_w == 0:
        return None
    anchored = np.unique(labelled_w[strong & (labelled_w > 0)])
    fg = np.isin(labelled_w, anchored[anchored > 0])

    fg = ndimage.binary_opening(fg, np.ones((5, 5)))
    fg = ndimage.binary_fill_holes(fg)

    labelled, count = ndimage.label(fg)
    if count == 0:
        return None
    sizes = ndimage.sum(fg, labelled, range(1, count + 1))

    # Prefer the blob the photographer centred, not simply the largest: a
    # flat-lay often catches other objects at the edges of the frame.
    cy, cx = h / 2, w / 2
    diag = np.hypot(cy, cx)
    best_j, best_score = None, -np.inf
    for j in range(1, count + 1):
        if sizes[j - 1] < fg.size * MIN_AREA_FRAC:
            continue
        ys, xs = np.where(labelled == j)
        offset = np.hypot(ys.mean() - cy, xs.mean() - cx) / diag
        score = sizes[j - 1] * (1.0 - 0.7 * offset)
        if score > best_score:
            best_j, best_score = j, score

    if best_j is None:
        return None
    blob = ndimage.binary_fill_holes(labelled == best_j)

    # The border-sampled model is global, so it judges a mid-grey suede panel
    # against the whole surface rather than against the bed right next to it,
    # and bites chunks out of the shoe. One local pass with colour models fitted
    # to this blob's own interior and its immediate surroundings closes them.
    # A wider band than the worn-garment path, because these bites run deep.
    # Veto, mirroring what the model's background labels do for a worn garment:
    # the local pass may only claim pixels the global surface model already
    # found doubtful. Without it the repair also swallowed bed in shadow, which
    # is as dark as the shoe's mesh and indistinguishable to a local model.
    band = max(8, round(max(blob.shape) * FLATLAY_REFINE_BAND_FRAC))
    eligible = dist > weak_t * FLATLAY_ELIGIBLE_RATIO
    grown = _colour_grow(blob, rgb, band, eligible)
    return ndimage.binary_fill_holes(ndimage.binary_closing(grown, np.ones((5, 5))))


def _person_score(probs: np.ndarray) -> tuple[float, float]:
    """(fraction of frame, mean confidence) for pixels that require a person."""
    labels = probs.argmax(axis=0)
    person = np.isin(labels, PERSON_PART_IDS)
    if not person.any():
        return 0.0, 0.0
    return float(person.mean()), float(probs.max(axis=0)[person].mean())


def extract_garments(img: Image.Image, user_id: int, complete: bool = False) -> dict:
    """Returns {"items": [...], "notice": str | None}.

    `notice` is set when the photo cannot be segmented meaningfully, so the
    caller can tell the user instead of silently storing a wrong guess.
    `complete` paints in the parts of each worn garment a hand, arm, hair or bag
    hid, and adds a `filled` fraction to each item. It is skipped quietly when
    the LaMa weights are not installed.
    """
    source = img.convert("RGB")
    work = _resize_to(source, settings.WORK_SIDE)
    probs = _predict(work)
    certainty = probs.max(axis=0)
    rgb = np.array(work).astype(np.float32)
    frame_area = work.width * work.height
    feather_width = max(1.5, max(work.size) / 640)

    person_frac, person_conf = _person_score(probs)
    if person_frac < MIN_PERSON_FRAC or person_conf < MIN_PERSON_CONF:
        # Matting is trained for object-vs-background, which is precisely what a
        # flat-lay needs and what colour alone cannot do once the garment and
        # the surface share a shade.
        matte = matting.subject_matte(work)
        if matte is not None:
            alpha = (matte * 255).astype(np.uint8)
            mask = matte > 0.5
        else:
            mask = _flatlay_mask(rgb)
            if mask is not None:
                alpha = _feather_alpha(mask, feather_width)

        if mask is None or mask.mean() > FLATLAY_MAX_AREA or mask.mean() < MIN_AREA_FRAC:
            return {
                "items": [],
                "notice": ("This photo could not be separated into clothing. Try a "
                           "picture of the outfit being worn, or lay the piece on a "
                           "plain surface."),
            }

        ys, xs = np.where(alpha > 8)
        crop = _compose_crop(source, alpha, (ys.min(), ys.max(), xs.min(), xs.max()))
        core = ndimage.binary_erosion(mask, np.ones((5, 5)))
        stored_name, file_bytes = save_garment_crop(crop, user_id)

        return {
            "items": [{
                "name": "Untitled piece",
                # Nothing here identifies *what* the garment is -- there is no
                # person to place it on -- so the user names and files it.
                "category": "other",
                "stored_name": stored_name,
                "color": _dominant_color(rgb.astype(np.uint8), core if core.any() else mask),
                "bytes": file_bytes,
                "confidence": None,
                "image_url": f"/api/images/item/{stored_name}",
            }],
            "notice": ("No one is visible, so this was cut out as a single piece. "
                       "Give it a name and pick a category."),
        }

    # One matte for the whole photo, shared by every garment in it.
    subject = matting.subject_matte(work)

    if complete:
        from backend import flatten
        try:
            flatten._load_lama()
        except flatten.ModelMissing:
            complete = False
    labels = probs.argmax(axis=0) if complete else None

    results = []
    waist_up_dress = None
    for group in GARMENT_GROUPS:
        mask = _group_mask(probs, group["ids"])
        if mask.sum() < frame_area * MIN_AREA_FRAC:
            continue

        mask = _clean_mask(mask, group["parts"])
        reason = _reject(mask, certainty, frame_area)
        if reason:
            continue

        # How sure the model is about its own labelling here, which is what
        # decides whether the colour refinement is worth running.
        score = float(certainty[mask].mean())
        if score < REFINE_BELOW:
            mask = _clean_mask(_refine_mask(mask, rgb, probs), group["parts"])
            if _reject(mask, certainty, frame_area):
                continue

        hidden = None
        if complete:
            hidden = _hidden_part(mask, labels, max(work.size))
            if not mask.sum() * COMPLETE_MIN_FRAC <= hidden.sum() <= mask.sum() * COMPLETE_MAX_FRAC:
                hidden = None

        alpha = _feather_alpha(mask if hidden is None else mask | hidden, feather_width)

        if subject is not None:
            # SegFormer says which garment each pixel is; the matte says where
            # the person stops. Multiplying keeps garment-to-garment seams
            # exactly as SegFormer drew them -- the matte is ~1 inside the body
            # so those are untouched -- while the silhouette against sky, ground
            # or wall gets a real fractional alpha instead of a distance-field
            # guess. Anything the refinement absorbed from outside the person,
            # such as the balustrade behind the shoes, falls away here.
            alpha = (alpha.astype(np.float32) * subject).astype(np.uint8)
            if (alpha > 8).sum() < frame_area * MIN_AREA_FRAC:
                continue

        ys, xs = np.where(alpha > 8)
        box = (ys.min(), ys.max(), xs.min(), xs.max())
        crop = _compose_crop(source, alpha, box)
        if hidden is not None:
            crop = _fill_hidden(crop, hidden[box[0]:box[1] + 1, box[2]:box[3] + 1])
            mask = mask & ~hidden   # the colour comes from real fabric only

        # Colour sampled from the confident interior, away from the soft edge.
        core = ndimage.binary_erosion(mask, np.ones((5, 5)))
        if not core.any():
            core = mask

        stored_name, file_bytes = save_garment_crop(crop, user_id)

        results.append({
            "name": group["name"],
            "category": group["category"],
            "stored_name": stored_name,
            "color": _dominant_color(rgb.astype(np.uint8), core),
            "bytes": file_bytes,
            "confidence": round(score, 3),
            "image_url": f"/api/images/item/{stored_name}"
        })
        # Bottom 2%, not the last row: _clean_mask's closing trims the frame edge.
        if group["name"] == "Dress" and mask[-max(4, mask.shape[0] // 50):].any():
            waist_up_dress = results[-1]
        if complete:
            results[-1]["filled"] = 0.0 if hidden is None else round(float(hidden.sum() / (mask.sum() + hidden.sum())), 3)

    # This model labels a waist-up T-shirt "Dress" (0% Upper-clothes, 16% Dress on
    # real photos). Cut off by the frame bottom with no top or trousers beside it,
    # it is a top; a real dress in a full-length photo ends above the frame edge.
    if waist_up_dress is not None and not any(
            r["category"] in ("topwear", "bottomwear") for r in results):
        waist_up_dress.update(name="Top", category="topwear")

    notice = None
    if not results:
        notice = ("No clothing could be separated from this photo. Try a shot "
                  "where the full outfit is visible.")

    return {"items": results, "notice": notice}
