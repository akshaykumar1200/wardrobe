"""
segmenter.py for f5

Dual-model extraction pipeline: SegFormer + BiRefNet.
Feathering with signed distance fields, colour grow sole repair, flat-lay branch, and pattern/color extraction.
"""

import io
import uuid
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
from PIL import Image, ImageOps
from scipy import ndimage
from transformers import SegformerImageProcessor, AutoModelForSemanticSegmentation

import matting
from pattern import analyze_garment

MODEL_ID = "mattmdjaga/segformer_b2_clothes"
ITEMS_DIR = Path("storage/items")
ITEMS_DIR.mkdir(parents=True, exist_ok=True)

INFERENCE_SIDE = 1024
WORK_SIDE = 1280
TORCH_THREADS = 4

torch.set_num_threads(TORCH_THREADS)

# Load SegFormer once at startup
processor = SegformerImageProcessor.from_pretrained(MODEL_ID)
model = AutoModelForSemanticSegmentation.from_pretrained(MODEL_ID)
model.eval()

# Garment mapping aligned directly to f5 category conventions
GARMENT_GROUPS = [
    {"ids": (4,),     "category": "upper",     "name": "Top",        "parts": 1},
    {"ids": (5,),     "category": "lower",     "name": "Skirt",      "parts": 1},
    {"ids": (6,),     "category": "lower",     "name": "Trousers",   "parts": 2},
    {"ids": (7,),     "category": "full",      "name": "Dress",      "parts": 1},
    {"ids": (9, 10),  "category": "footwear",  "name": "Shoes",      "parts": 2},
    {"ids": (1,),     "category": "headwear",  "name": "Hat",        "parts": 1},
    {"ids": (3,),     "category": "headwear",  "name": "Sunglasses", "parts": 2},
    {"ids": (16,),    "category": "bag",       "name": "Bag",        "parts": 1},
]

MIN_AREA_FRAC = 0.004
MAX_AREA_FRAC = 0.60
MIN_FILL_RATIO = 0.15
MIN_CONFIDENCE = 0.55
PART_MIN_FRAC = 0.12

REFINE_BELOW = 0.85
REFINE_BAND_FRAC = 0.011
REFINE_BG_GATE = 0.995
REFINE_FG_CLUSTERS = 3
REFINE_BG_CLUSTERS = 5
MIN_ADDED_COMPONENT = 60

BACKGROUND_ID = 0
PERSON_PART_IDS = (2, 11, 12, 13, 14, 15)
MIN_PERSON_FRAC = 0.005
MIN_PERSON_CONF = 0.65

FLATLAY_BORDER = 0.06
FLATLAY_CLUSTERS = 4
FLATLAY_MARGIN = 1.25
FLATLAY_WEAK_RATIO = 0.85
FLATLAY_MIN_THRESHOLD = 6.0
FLATLAY_REFINE_BAND_FRAC = 0.030
FLATLAY_ELIGIBLE_RATIO = 0.6
FLATLAY_MAX_AREA = 0.75


def _resize_to(img: Image.Image, max_side: int) -> Image.Image:
    if max(img.size) <= max_side:
        return img
    scale = max_side / max(img.size)
    new_size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
    return img.resize(new_size, Image.LANCZOS)


def _predict(img: Image.Image) -> np.ndarray:
    small = _resize_to(img, INFERENCE_SIDE)
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
    inside = probs[list(ids)].sum(axis=0)
    outside = np.delete(probs, list(ids), axis=0).max(axis=0)
    return inside > outside


def _kmeans(x: np.ndarray, k: int, iters: int = 15) -> tuple[np.ndarray, np.ndarray]:
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
    if k <= 1 or len(points) < k * 20:
        groups = [points]
    else:
        _, labels = _kmeans(points, k)
        groups = [points[labels == j] for j in range(k)]

    model_g = []
    for g in groups:
        if len(g) < 20:
            continue
        cov = np.cov(g.T) + np.eye(3) * 25.0
        model_g.append((g.mean(axis=0), np.linalg.inv(cov),
                        float(np.log(np.linalg.det(cov))),
                        float(np.log(max(len(g) / len(points), 1e-6)))))
    return model_g


def _max_loglik(px: np.ndarray, model_g: list[tuple]) -> np.ndarray:
    best = np.full(len(px), -np.inf, np.float32)
    for mu, inv, logdet, logw in model_g:
        delta = px - mu
        ll = (-0.5 * np.einsum("ij,jk,ik->i", delta, inv, delta)
              - 0.5 * logdet + logw)
        best = np.maximum(best, ll.astype(np.float32))
    return best


def _colour_grow(mask: np.ndarray, rgb: np.ndarray, band_px: int,
                 eligible: np.ndarray | None = None) -> np.ndarray:
    core = ndimage.binary_erosion(mask, np.ones((7, 7)))
    if core.sum() < 200:
        return mask

    dist = ndimage.distance_transform_edt(~mask)
    candidates = (dist > 0) & (dist <= band_px)
    if eligible is not None:
        candidates &= eligible
    reference = (dist > band_px) & (dist <= band_px + 12)

    if candidates.sum() < 50 or reference.sum() < 200:
        return mask

    px = rgb[candidates]
    fg_model = _fit_clusters(rgb[core], REFINE_FG_CLUSTERS)
    bg_model = _fit_clusters(rgb[reference], REFINE_BG_CLUSTERS)
    if not fg_model or not bg_model:
        return mask

    claim = _max_loglik(px, fg_model) > _max_loglik(px, bg_model)

    grown = np.zeros_like(mask)
    ys, xs = np.where(candidates)
    grown[ys[claim], xs[claim]] = True

    labelled, count = ndimage.label(grown)
    if count:
        sizes = ndimage.sum(grown, labelled, range(1, count + 1))
        keep = [i + 1 for i, s in enumerate(sizes) if s >= MIN_ADDED_COMPONENT]
        grown = np.isin(labelled, keep)

    return mask | grown


def _refine_mask(mask: np.ndarray, rgb: np.ndarray, probs: np.ndarray) -> np.ndarray:
    labels = probs.argmax(axis=0)
    certainty = probs.max(axis=0)
    eligible = (labels == BACKGROUND_ID) & (certainty <= REFINE_BG_GATE)
    band_px = max(6, round(max(mask.shape) * REFINE_BAND_FRAC))
    return _colour_grow(mask, rgb, band_px, eligible)


def _keep_components(mask: np.ndarray, max_parts: int) -> np.ndarray:
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
    mask = ndimage.binary_closing(mask, np.ones((5, 5)))
    mask = _keep_components(mask, max_parts)
    return ndimage.binary_fill_holes(mask)


def _feather_alpha(mask: np.ndarray, width: float) -> np.ndarray:
    inside = ndimage.distance_transform_edt(mask)
    outside = ndimage.distance_transform_edt(~mask)
    signed = inside - outside
    alpha = np.clip(signed / width + 0.5 - 0.25, 0.0, 1.0)
    return (alpha * 255).astype(np.uint8)


def _reject(mask: np.ndarray, certainty: np.ndarray, frame_area: int) -> str | None:
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


def _compose_crop(source: Image.Image, alpha: np.ndarray, box: tuple) -> Image.Image:
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
    h, w = rgb.shape[:2]
    by, bx = max(1, int(h * FLATLAY_BORDER)), max(1, int(w * FLATLAY_BORDER))
    edge = np.zeros((h, w), bool)
    edge[:by, :] = edge[-by:, :] = True
    edge[:, :bx] = edge[:, -bx:] = True

    sample = rgb[edge][::7]
    if len(sample) < 200:
        return None

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

    band = max(8, round(max(blob.shape) * FLATLAY_REFINE_BAND_FRAC))
    eligible = dist > weak_t * FLATLAY_ELIGIBLE_RATIO
    grown = _colour_grow(blob, rgb, band, eligible)
    return ndimage.binary_fill_holes(ndimage.binary_closing(grown, np.ones((5, 5))))


def _person_score(probs: np.ndarray) -> tuple[float, float]:
    labels = probs.argmax(axis=0)
    person = np.isin(labels, PERSON_PART_IDS)
    if not person.any():
        return 0.0, 0.0
    return float(person.mean()), float(probs.max(axis=0)[person].mean())


def extract_garments(raw_bytes: bytes) -> list[dict]:
    """
    Extracts garments from raw photo bytes.
    Returns a list of dicts: {"category", "path", "color", "label", "colors", "pattern", "scale", "confidence"}
    """
    img = Image.open(io.BytesIO(raw_bytes))
    img = ImageOps.exif_transpose(img)
    source = img.convert("RGB")

    work = _resize_to(source, WORK_SIDE)
    probs = _predict(work)
    certainty = probs.max(axis=0)
    rgb = np.array(work).astype(np.float32)
    frame_area = work.width * work.height
    feather_width = max(1.5, max(work.size) / 640)

    person_frac, person_conf = _person_score(probs)
    is_worn = not (person_frac < MIN_PERSON_FRAC or person_conf < MIN_PERSON_CONF)

    results = []

    if not is_worn:
        # FLAT-LAY path
        matte = matting.subject_matte(work)
        if matte is not None:
            alpha = (matte * 255).astype(np.uint8)
            mask = matte > 0.5
        else:
            mask = _flatlay_mask(rgb)
            if mask is not None:
                alpha = _feather_alpha(mask, feather_width)
            else:
                alpha = None

        if mask is not None and mask.mean() <= FLATLAY_MAX_AREA and mask.mean() >= MIN_AREA_FRAC:
            ys, xs = np.where(alpha > 8)
            crop = _compose_crop(source, alpha, (ys.min(), ys.max(), xs.min(), xs.max()))
            
            analysis = analyze_garment(crop, category="upper", name="Untitled Piece")

            filename = f"{uuid.uuid4().hex}.png"
            out_path = ITEMS_DIR / filename
            crop.save(out_path, optimize=True)

            results.append({
                "category": "upper",
                "label": "Untitled Piece",
                "path": f"/storage/items/{filename}",
                "color": analysis["color_hex"],
                "color_name": analysis["color_name"],
                "colors": analysis["colors"],
                "pattern": analysis["pattern"],
                "scale": analysis["scale"],
                "pixels": analysis["area"],
                "confidence": None,
                "is_flatlay": True
            })
    else:
        # WORN path
        subject = matting.subject_matte(work)

        for group in GARMENT_GROUPS:
            mask = _group_mask(probs, group["ids"])
            if mask.sum() < frame_area * MIN_AREA_FRAC:
                continue

            mask = _clean_mask(mask, group["parts"])
            reason = _reject(mask, certainty, frame_area)
            if reason:
                continue

            score = float(certainty[mask].mean())
            if score < REFINE_BELOW:
                refined = _refine_mask(mask, rgb, probs)
                mask = _clean_mask(refined, group["parts"])
                if _reject(mask, certainty, frame_area):
                    continue

            alpha = _feather_alpha(mask, feather_width)

            if subject is not None:
                alpha = (alpha.astype(np.float32) * subject).astype(np.uint8)
                if (alpha > 8).sum() < frame_area * MIN_AREA_FRAC:
                    continue

            ys, xs = np.where(alpha > 8)
            box = (ys.min(), ys.max(), xs.min(), xs.max())
            crop = _compose_crop(source, alpha, box)

            analysis = analyze_garment(crop, category=group["category"], name=group["name"])

            filename = f"{uuid.uuid4().hex}.png"
            out_path = ITEMS_DIR / filename
            crop.save(out_path, optimize=True)

            results.append({
                "category": group["category"],
                "label": group["name"],
                "path": f"/storage/items/{filename}",
                "color": analysis["color_hex"],
                "color_name": analysis["color_name"],
                "colors": analysis["colors"],
                "pattern": analysis["pattern"],
                "scale": analysis["scale"],
                "pixels": analysis["area"],
                "confidence": round(score, 3),
                "is_flatlay": False
            })

    return results
