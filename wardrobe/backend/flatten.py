"""Turn a worn, front-facing top into a symmetric product-style view."""
from __future__ import annotations

import io
import threading
import time

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage
from scipy.interpolate import RBFInterpolator
from scipy.ndimage import map_coordinates

from backend import segmenter
from backend.config import settings

CANVAS = 768
MARGIN = 0.06
SLEEVE_ANGLE_DEG = 35
HEM_EXTEND = 0.07
CUFF_BAND = 0.08
HEM_BAND = 0.12
LIGHT_SIGMA = 0.045 * CANVAS


class NotSuitable(ValueError):
    """The photo does not contain a usable front-facing top."""


class ModelMissing(RuntimeError):
    """The optional LaMa weights are not installed on this server."""


_lama = None
_lama_lock = threading.Lock()


def _load_lama():
    global _lama
    if _lama is None:
        with _lama_lock:
            if _lama is None:
                from pathlib import Path
                if not Path(settings.LAMA_MODEL_PATH).is_file():
                    raise ModelMissing()
                try:
                    _lama = torch.jit.load(settings.LAMA_MODEL_PATH, map_location="cpu").eval()
                except (OSError, RuntimeError) as exc:
                    if not Path(settings.LAMA_MODEL_PATH).is_file():
                        raise ModelMissing() from exc
                    raise
    return _lama


def _class_ids():
    labels = segmenter.model.config.id2label
    names = {str(v).strip().lower().replace("_", "-"): int(k) for k, v in labels.items()}
    def lookup(*wanted):
        got = [v for k, v in names.items() if any(k == w or k.endswith("-" + w) for w in wanted)]
        if not got:
            raise NotSuitable("The segmentation model is missing required clothing labels.")
        return got
    return lookup


def _landmarks(mask, arms, hem_extended):
    h, w = mask.shape
    ys, xs = np.where(mask)
    if not len(xs):
        raise NotSuitable("No top could be found in this photo.")
    if len(xs) < h * w * .02:
        raise NotSuitable("The top is too small in this photo.")
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    if bh / max(1, bw) < .6 or bh / max(1, bw) > 2.5:
        raise NotSuitable("The top's shape is too unusual for a reliable flat view.")
    cx = float(xs.mean())
    top = np.full(w, h, dtype=int)
    for x in range(x0, x1 + 1):
        yy = np.where(mask[:, x])[0]
        if len(yy): top[x] = yy[0]
    leftxs = np.arange(max(x0, int(np.floor(cx - .3 * bw))), min(x1 + 1, int(np.ceil(cx))))
    rightxs = np.arange(max(x0, int(np.floor(cx)) + 1), min(x1 + 1, int(np.ceil(cx + .3 * bw))))
    if not len(leftxs) or not len(rightxs) or np.all(top[leftxs] == h) or np.all(top[rightxs] == h):
        raise NotSuitable("The neckline is not visible clearly enough.")
    nlx, nrx = int(leftxs[np.argmin(top[leftxs])]), int(rightxs[np.argmin(top[rightxs])])
    nly, nry = int(top[nlx]), int(top[nrx])
    if nly == h or nry == h: raise NotSuitable("The neckline is not visible clearly enough.")
    collarxs = np.arange(nlx, nrx + 1)
    cyx = int(collarxs[np.argmax(top[collarxs])])
    collar = np.array([cyx, int(top[cyx])], float)
    neck_l, neck_r = np.array([nlx, nly], float), np.array([nrx, nry], float)
    dilated_arms = ndimage.binary_dilation(arms, iterations=2)
    contact = mask & dilated_arms
    arm_labels, arm_count = ndimage.label(arms)
    result = {"neck_l": neck_l, "neck_r": neck_r, "collar": collar}
    for side, choose in (("l", lambda x: x < cx), ("r", lambda x: x > cx)):
        side_arm_ids = np.unique(arm_labels[:, :int(np.ceil(cx))] if side == "l" else arm_labels[:, int(np.floor(cx))+1:])
        side_arm_ids = side_arm_ids[side_arm_ids != 0]
        if len(side_arm_ids):
            sizes = np.bincount(arm_labels.ravel())
            arm_id = side_arm_ids[np.argmax(sizes[side_arm_ids])]
            arm_y = np.where(arm_labels == arm_id)[0]
            arm_top = int(arm_y.min())
            contact_band = contact & (np.indices(mask.shape)[0] <= arm_top + CUFF_BAND * bh)
        else:
            contact_band = np.zeros_like(contact)
        sy, sx = np.where(contact_band & choose(np.indices(mask.shape)[1]))
        if len(sx):
            order = np.argsort(np.abs(sx - cx))
            inner_i, outer_i = order[0], order[-1]
            cuff_inner = np.array([sx[inner_i], sy[inner_i]], float)
            cuff_outer = np.array([sx[outer_i], sy[outer_i]], float)
        else:
            side_x = xs[xs < cx] if side == "l" else xs[xs > cx]
            ex = int(side_x.min() if side == "l" else side_x.max())
            outer_ys = np.where(mask[:, ex])[0]
            ey = int(outer_ys[0])
            cuff_outer = np.array([ex, ey], float)
            neck = neck_l if side == "l" else neck_r
            iy = int(np.clip(round(neck[1] + .25*bh), y0, y1))
            row = np.where(mask[iy])[0]
            row = row[row < cx] if side == "l" else row[row > cx]
            if not len(row):
                raise NotSuitable("The sleeve edge is not visible clearly enough.")
            ix = int(row.max() if side == "l" else row.min())
            cuff_inner = np.array([ix, iy], float)
        neck = neck_l if side == "l" else neck_r
        shoulder_x = neck[0] + .55 * (cuff_outer[0] - neck[0])
        shx = int(np.clip(round(shoulder_x), x0, x1))
        shy = int(top[shx]) if top[shx] < h else int(neck[1])
        result.update({f"cuff_outer_{side}": cuff_outer, f"cuff_inner_{side}": cuff_inner,
                       f"armpit_{side}": cuff_inner, f"shoulder_{side}": np.array([shx, shy], float)})
    bottom = np.full(w, -1, int)
    for x in range(x0, x1 + 1):
        yy = np.where(mask[:, x])[0]
        if len(yy): bottom[x] = yy[-1]
    low = int(bottom.max())
    hem_pixels = mask & (np.indices(mask.shape)[0] >= y1 - HEM_BAND * bh)
    hem_xs = np.where(hem_pixels)[1]
    lx, rx = int(np.percentile(hem_xs, 5)), int(np.percentile(hem_xs, 95))
    centre_x = int(np.clip(round(cx), x0, x1))
    hc_y = int(bottom[centre_x]) if bottom[centre_x] >= 0 else low
    extended = bool(mask[-1].any())
    dy = .07 * bh if extended else 0
    result.update({"hem_l": np.array([lx, low + dy]), "hem_r": np.array([rx, low + dy]),
                   "hem_c": np.array([cx, hc_y + dy])})
    for side in ("l", "r"):
        ax = result[f"armpit_{side}"]
        if low + dy <= ax[1]: raise NotSuitable("The visible hem does not extend below the arms.")
        row = int(np.clip(round((ax[1] + low) / 2), y0, y1))
        rowxs = np.where(mask[row])[0]
        rowxs = rowxs[rowxs < cx] if side == "l" else rowxs[rowxs > cx]
        if not len(rowxs): raise NotSuitable("The shirt sides are not visible clearly enough.")
        bx = rowxs.min() if side == "l" else rowxs.max()
        result[f"body_{side}"] = np.array([bx, row], float)
    result["chest"] = collar + .30 * (result["hem_c"] - collar)
    result["stomach"] = collar + .70 * (result["hem_c"] - collar)
    if abs(result["cuff_outer_l"][0] - cx) <= abs(result["shoulder_l"][0] - cx) or abs(result["cuff_outer_r"][0] - cx) <= abs(result["shoulder_r"][0] - cx):
        raise NotSuitable("The sleeves are not visible clearly enough.")
    return result


def _lab_even(rgb, valid):
    # This broad correction cannot remove sharp cast shadows.
    s = rgb.astype(np.float32) / 255
    lin = np.where(s <= .04045, s / 12.92, ((s + .055) / 1.055) ** 2.4)
    Y = lin @ np.array([.2126, .7152, .0722], np.float32)
    sigma = LIGHT_SIGMA
    den = ndimage.gaussian_filter(valid.astype(np.float32), sigma)
    num = ndimage.gaussian_filter(Y * valid, sigma)
    illum = num / np.maximum(den, 1e-4)
    gain = np.clip(float(np.median(Y[valid])) / np.maximum(illum, 1e-8), .5, 2.0)
    lin *= gain[..., None]
    srgb = np.where(lin <= .0031308, 12.92*lin, 1.055*np.maximum(lin,0)**(1/2.4)-.055)
    return np.clip(srgb*255, 0, 255).astype(np.uint8)


def _check_warp_folds(warp, silhouette):
    h, w = silhouette.shape
    yy, xx = np.mgrid[0:h:8, 0:w:8]
    nx, ny = np.minimum(xx+8, w-1), np.minimum(yy+8, h-1)
    inside = silhouette[yy, xx] & silhouette[yy, nx] & silhouette[ny, xx]
    points = np.column_stack((xx[inside], yy[inside])).astype(float)
    if not len(points):
        return
    px = points + (8, 0)
    py = points + (0, 8)
    f = warp(points)
    fx, fy = warp(px), warp(py)
    dx, dy = fx-f, fy-f
    det = dx[:, 0]*dy[:, 1] - dy[:, 0]*dx[:, 1]
    if np.mean(det <= 0) > .01:
        raise NotSuitable("Couldn't map this photo to a flat shape cleanly. A front-facing photo with arms slightly away from the body works best.")


def _lama_fill(rgb, holes):
    model = _load_lama()
    ys, xs = np.where(ndimage.binary_dilation(holes, iterations=8))
    if not len(xs): return rgb
    y0, y1 = max(0, ys.min()-64), min(rgb.shape[0], ys.max()+65)
    x0, x1 = max(0, xs.min()-64), min(rgb.shape[1], xs.max()+65)
    crop = rgb[y0:y1, x0:x1].copy()
    mask = holes[y0:y1, x0:x1]
    ph, pw = (-crop.shape[0]) % 8, (-crop.shape[1]) % 8
    tensor = torch.from_numpy(crop.astype(np.float32)/255).permute(2,0,1)[None]
    mt = torch.from_numpy(mask.astype(np.float32))[None,None]
    tensor = torch.nn.functional.pad(tensor, (0,pw,0,ph), mode="reflect")
    mt = torch.nn.functional.pad(mt, (0,pw,0,ph), value=1)
    with torch.no_grad(): out = model(tensor, mt)
    if isinstance(out, (tuple, list)): out = out[0]
    arr = out[0,:,:crop.shape[0],:crop.shape[1]].permute(1,2,0).clamp(0,1).numpy()
    result = rgb.copy()
    section = result[y0:y1,x0:x1]
    section[mask] = (arr[mask]*255).astype(np.uint8)
    return result


def flatten_top(photo: Image.Image) -> tuple[bytes, dict]:
    started = time.perf_counter()
    source = segmenter._resize_to(photo.convert("RGB"), settings.WORK_SIDE)
    probs = segmenter._predict(source)
    labels = probs.argmax(axis=0)
    lookup = _class_ids()
    garment_labels = lookup("upper-clothes", "dress")
    arm_labels = lookup("left-arm", "right-arm")
    neck_labels = lookup("face", "hair")
    raw = np.isin(labels, garment_labels)
    components, count = ndimage.label(raw)
    if not count: raise NotSuitable("No top could be found in this photo.")
    sizes = np.bincount(components.ravel()); sizes[0] = 0
    mask = ndimage.binary_fill_holes(components == sizes.argmax())
    arms = np.isin(labels, arm_labels)
    lm = _landmarks(mask, arms, False)
    height, width = mask.shape
    # Build a proportion-matched symmetric target using corresponding measured spans.
    nw = np.linalg.norm(lm["neck_r"]-lm["neck_l"])
    collar_depth = max(1., lm["collar"][1] - min(lm["neck_l"][1], lm["neck_r"][1]))
    shoulder_half = (abs(lm["shoulder_l"][0]-lm["collar"][0]) + abs(lm["shoulder_r"][0]-lm["collar"][0]))/2
    sleeve = (np.linalg.norm(lm["shoulder_l"]-lm["cuff_outer_l"]) + np.linalg.norm(lm["shoulder_r"]-lm["cuff_outer_r"])) / 2
    cuff = (np.linalg.norm(lm["cuff_outer_l"]-lm["cuff_inner_l"]) + np.linalg.norm(lm["cuff_outer_r"]-lm["cuff_inner_r"])) / 2
    bodyw = max(abs(lm["hem_r"][0]-lm["hem_l"][0]), abs(lm["body_r"][0]-lm["body_l"][0]))
    bodylen = np.linalg.norm(lm["hem_c"]-lm["collar"])
    # Unscaled canonical coordinates preserve measured dimensions and angle, then fit the silhouette to the square.
    c = CANVAS/2
    angle = np.deg2rad(SLEEVE_ANGLE_DEG)
    nY = 70.; scale0 = 1.
    shoulder_y = nY+max(collar_depth,22)
    t = {
        "neck_l": np.array([c-nw/2,nY]), "neck_r": np.array([c+nw/2,nY]),
        "collar": np.array([c,nY+collar_depth]),
        "shoulder_l": np.array([c-shoulder_half,nY+max(collar_depth,22)]),
        "shoulder_r": np.array([c+shoulder_half,nY+max(collar_depth,22)]),
        "cuff_outer_l": np.array([c-shoulder_half-sleeve*np.cos(angle),shoulder_y+sleeve*np.sin(angle)]),
        "cuff_outer_r": np.array([c+shoulder_half+sleeve*np.cos(angle),shoulder_y+sleeve*np.sin(angle)]),
        "cuff_inner_l": np.array([c-shoulder_half-sleeve*np.cos(angle)+cuff*np.sin(angle),shoulder_y+sleeve*np.sin(angle)+cuff*np.cos(angle)]),
        "cuff_inner_r": np.array([c+shoulder_half+sleeve*np.cos(angle)-cuff*np.sin(angle),shoulder_y+sleeve*np.sin(angle)+cuff*np.cos(angle)]),
        "hem_l": np.array([c-bodyw/2,nY+bodylen]), "hem_r": np.array([c+bodyw/2,nY+bodylen]), "hem_c": np.array([c,nY+bodylen]),
        "body_l": np.array([c-bodyw/2,nY+(nY+bodylen-nY)*.62]), "body_r": np.array([c+bodyw/2,nY+(nY+bodylen-nY)*.62]),
        "chest": np.array([c,nY+bodylen*.30]), "stomach": np.array([c,nY+bodylen*.70]),
    }
    armhole_l = float(np.clip(lm["armpit_l"][1]-lm["shoulder_l"][1], .12*bodylen, .35*bodylen))
    armhole_r = float(np.clip(lm["armpit_r"][1]-lm["shoulder_r"][1], .12*bodylen, .35*bodylen))
    t["armpit_l"] = np.array([c-bodyw/2, shoulder_y+armhole_l])
    t["armpit_r"] = np.array([c+bodyw/2, shoulder_y+armhole_r])
    outline = ["neck_l","shoulder_l","cuff_outer_l","cuff_inner_l","armpit_l","body_l","hem_l","hem_c","hem_r","body_r","armpit_r","cuff_inner_r","cuff_outer_r","shoulder_r","neck_r","collar"]
    pts = np.array([t[k] for k in outline]); lo, hi = pts.min(0), pts.max(0)
    fit = min(CANVAS*(1-2*MARGIN)/(hi[0]-lo[0]), CANVAS*(1-2*MARGIN)/(hi[1]-lo[1]))
    for k in t: t[k] = (t[k]-(lo+hi)/2)*fit + c
    poly = Image.new("L", (CANVAS,CANVAS)); ImageDraw.Draw(poly).polygon([tuple(t[k]) for k in outline], fill=255)
    poly = poly.filter(ImageFilter.GaussianBlur(1.2)); silhouette = np.asarray(poly) > 127
    keys = [k for k in outline if k not in ("armpit_l", "armpit_r")] + ["chest","stomach"]
    target_pts = np.array([t[k] for k in keys]); source_pts = np.array([lm[k] for k in keys])
    warp = RBFInterpolator(target_pts, source_pts, kernel="thin_plate_spline", smoothing=1.0)
    _check_warp_folds(warp, silhouette)
    yy, xx = np.where(silhouette)
    mapped = warp(np.column_stack((xx,yy)))
    srcx, srcy = mapped[:,0], mapped[:,1]
    eroded = ndimage.binary_erosion(mask, iterations=3)
    ix, iy = np.rint(srcx).astype(int), np.rint(srcy).astype(int)
    inside = (ix>=0)&(ix<width)&(iy>=0)&(iy<height)
    real = np.zeros(len(xx), bool)
    real[inside] = eroded[iy[inside],ix[inside]] & ~arms[iy[inside],ix[inside]]
    photo_arr = np.asarray(source).astype(np.float32)
    warped = np.zeros((CANVAS,CANVAS,3), np.uint8)
    for ch in range(3): warped[yy,xx,ch] = np.clip(map_coordinates(photo_arr[:,:,ch], [srcy,srcx], order=1, mode="nearest"),0,255).astype(np.uint8)
    valid = np.zeros((CANVAS,CANVAS), bool); valid[yy[real],xx[real]] = True
    if not valid.any(): raise NotSuitable("The top has too few visible fabric pixels to flatten.")
    warped = _lab_even(warped, valid)
    median = np.median(warped[valid], axis=0).astype(np.uint8)
    warped[~silhouette] = median
    holes = silhouette & ~valid
    warped = _lama_fill(warped, holes)
    alpha = np.asarray(poly, dtype=np.uint8)
    out = Image.fromarray(np.dstack((warped,alpha)), "RGBA")
    buf = io.BytesIO(); out.save(buf, "PNG", optimize=True)
    return buf.getvalue(), {"real_fraction": float(valid.sum()/max(1,silhouette.sum())), "hem_extended": bool(mask[-1].any()), "seconds": round(time.perf_counter()-started, 3)}
