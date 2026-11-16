"""Measure the shirt's real colour from several photos, then recolour the TryOffDiff output.

1. The app's own clothing segmenter (mattmdjaga/segformer_b2_clothes) finds the
   upper-body garment in each photo.
2. Shirt pixels are pooled with every photo weighted equally, so close-ups do not
   outvote full-body shots and their lighting.
3. The generated shirt's L, a, b histograms are matched to that pool, which moves
   its colours onto the real ones while keeping the generated image's layout.

usage: python color_fix.py OUT_DIR photo1.jpg photo2.jpg ... -- generated1.png ...
"""

import sys

import cv2
import numpy as np
import torch
from PIL import Image, ImageDraw
from scipy import ndimage
from transformers import SegformerForSemanticSegmentation, SegformerImageProcessor

MODEL = "mattmdjaga/segformer_b2_clothes"
PER_PHOTO = 40_000   # pixels sampled from each photo, so each one counts the same
rng = np.random.default_rng(0)


def to_lab(rgb_u8):
    return cv2.cvtColor(rgb_u8.reshape(-1, 1, 3), cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)


def lab_to_hex(lab):
    rgb = cv2.cvtColor(np.clip(lab, 0, 255).astype(np.uint8).reshape(1, 1, 3), cv2.COLOR_LAB2RGB)[0, 0]
    return "#%02x%02x%02x" % tuple(int(c) for c in rgb)


def largest(mask):
    lab, n = ndimage.label(mask)
    if n == 0:
        return mask
    sizes = ndimage.sum(mask, lab, range(1, n + 1))
    return lab == (int(np.argmax(sizes)) + 1)


def delta_e(a, b):   # CIE76 on OpenCV's 8-bit Lab, rescaled to standard units
    s = np.array([100 / 255, 1, 1], np.float32)
    return float(np.linalg.norm((a - b) * s))


def main():
    out = sys.argv[1]
    split = sys.argv.index("--")
    photos, generated = sys.argv[2:split], sys.argv[split + 1:]

    proc = SegformerImageProcessor.from_pretrained(MODEL)
    model = SegformerForSemanticSegmentation.from_pretrained(MODEL).eval()
    # In waist-up shots the model calls a long T-shirt a Dress, so both count as the shirt.
    upper = [i for i, n in model.config.id2label.items() if n in ("Upper-clothes", "Dress")]

    pooled, thumbs, medians = [], [], []
    for p in photos:
        img = Image.open(p).convert("RGB")
        with torch.no_grad():
            logits = model(**proc(images=img, return_tensors="pt")).logits
        logits = torch.nn.functional.interpolate(logits, size=img.size[::-1], mode="bilinear", align_corners=False)
        mask = largest(np.isin(logits.argmax(1)[0].numpy(), upper))
        # Edge pixels blend into skin and sky; keep only the interior of the shirt.
        mask = ndimage.binary_erosion(mask, iterations=6)
        arr = np.array(img)
        lab = to_lab(arr[mask])
        take = lab[rng.choice(len(lab), size=min(PER_PHOTO, len(lab)), replace=False)]
        pooled.append(take)
        medians.append(np.median(lab, axis=0))
        viz = arr.copy()
        viz[~mask] = (viz[~mask] * 0.25).astype(np.uint8)
        t = Image.fromarray(viz); t.thumbnail((260, 260)); thumbs.append(t)
        print(f"{p.rsplit('/', 1)[-1]:8} shirt px={mask.sum():7d}  median colour {lab_to_hex(medians[-1])}")

    ref = np.concatenate(pooled)
    ref_median = np.median(ref, axis=0)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 0.5)
    _, labels, centers = cv2.kmeans(ref, 2, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    order = np.argsort(centers[:, 0])
    share = [(labels == i).mean() for i in order]
    spread = max(delta_e(m, ref_median) for m in medians)
    print(f"\nREAL SHIRT (all {len(photos)} photos, equal weight)")
    print(f"  overall median   : {lab_to_hex(ref_median)}")
    print(f"  base (darker)    : {lab_to_hex(centers[order[0]])}  {share[0]:.0%} of shirt")
    print(f"  wash (lighter)   : {lab_to_hex(centers[order[1]])}  {share[1]:.0%} of shirt")
    print(f"  photo-to-photo variation: up to dE {spread:.1f} from the pooled median (lighting)")

    rows = []
    for g in generated:
        arr = np.array(Image.open(g).convert("RGB"))
        border = np.concatenate([arr[:8].reshape(-1, 3), arr[-8:].reshape(-1, 3), arr[:, :8].reshape(-1, 3), arr[:, -8:].reshape(-1, 3)])
        bg = np.median(border, axis=0)
        mask = np.linalg.norm(arr.astype(np.float32) - bg, axis=2) > 30
        mask = ndimage.binary_erosion(largest(ndimage.binary_fill_holes(mask)), iterations=1)
        lab = to_lab(arr[mask])
        fixed = np.empty_like(lab)
        for c in range(3):   # quantile-map each Lab channel onto the real shirt's distribution
            src_q = np.argsort(np.argsort(lab[:, c])) / max(len(lab) - 1, 1)
            fixed[:, c] = np.quantile(ref[:, c], src_q)
        res = arr.copy()
        res[mask] = cv2.cvtColor(np.clip(fixed, 0, 255).astype(np.uint8).reshape(-1, 1, 3), cv2.COLOR_LAB2RGB).reshape(-1, 3)
        name = g.rsplit("/", 1)[-1].replace(".png", "_fixed.png")
        Image.fromarray(res).save(f"{out}/{name}")
        before, after = delta_e(np.median(lab, 0), ref_median), delta_e(np.median(fixed, 0), ref_median)
        print(f"\n{g.rsplit('/', 1)[-1]}: colour error vs real shirt  dE {before:.1f} -> {after:.1f}   (dE<2.3 is barely noticeable)")
        rows.append((Image.fromarray(arr), Image.fromarray(res), before, after, g.rsplit("/", 1)[-1]))

    # One sheet: the five masks, the measured swatches, before/after for each output.
    W = 5 * 270
    sheet = Image.new("RGB", (W, 300 + 90 + len(rows) * 330), "white")
    d = ImageDraw.Draw(sheet)
    d.text((6, 4), "Shirt found by the app's segmenter in each photo (everything else dimmed)", fill="black")
    for i, t in enumerate(thumbs):
        sheet.paste(t, (i * 270 + 5, 22))
    y = 300
    for i, (lab_c, label) in enumerate([(ref_median, "real: median"), (centers[order[0]], f"real: base {share[0]:.0%}"), (centers[order[1]], f"real: wash {share[1]:.0%}")]):
        hexc = lab_to_hex(lab_c)
        d.rectangle([i * 270 + 5, y, i * 270 + 265, y + 60], fill=hexc)
        d.text((i * 270 + 8, y + 64), f"{label}  {hexc}", fill="black")
    y += 90
    for before_img, after_img, b, a, name in rows:
        for j, (im, cap) in enumerate([(before_img, f"{name}: as generated  dE {b:.1f}"), (after_img, f"{name}: recoloured  dE {a:.1f}")]):
            t = im.copy(); t.thumbnail((310, 310))
            sheet.paste(t, (j * 330 + 5, y + 16)); d.text((j * 330 + 8, y), cap, fill="black")
        y += 330
    sheet.save(f"{out}/color_fix_sheet.png")
    print(f"\nsaved {out}/color_fix_sheet.png")


if __name__ == "__main__":
    main()
