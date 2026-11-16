"""
pattern.py

Problem 1: Garment color distribution, pattern classification, and pattern scale detection.

Given a garment image or cutout (RGBA or RGB):
1. extract_garment_colors: Extracts dominant colors, relative shares, and nearest named colors.
2. detect_pattern: Classifies pattern type ('solid', 'heather', 'striped', 'checkered', 'plaid', 'floral', 'polka_dot', 'graphic')
   and scale ('none', 'fine', 'medium', 'bold').
3. analyze_garment: Full pipeline returning the item dictionary ready for outfit_color.py.
"""

import numpy as np
from PIL import Image
from scipy import ndimage
from skimage.color import rgb2lab, deltaE_ciede2000

from colors import PALETTE, _hex_to_lab, get_nearest_color_name, _hex_to_rgb


def _extract_valid_pixels(img: Image.Image, max_dim: int = 400) -> tuple[np.ndarray, np.ndarray]:
    """Resize image and return (RGB pixels array Nx3, 2D mask bool)."""
    # Resize for fast, robust analysis
    scale = min(1.0, max_dim / max(img.size))
    if scale < 1.0:
        new_w, new_h = max(1, int(img.width * scale)), max(1, int(img.height * scale))
        work = img.resize((new_w, new_h), Image.LANCZOS)
    else:
        work = img

    arr = np.array(work)
    if arr.ndim == 3 and arr.shape[2] == 4:
        alpha = arr[..., 3]
        mask = alpha > 30
        # Erode mask slightly to avoid background fringes
        eroded = ndimage.binary_erosion(mask, np.ones((3, 3)))
        if eroded.sum() > 200:
            mask = eroded
        rgb = arr[..., :3]
    else:
        mask = np.ones((arr.shape[0], arr.shape[1]), dtype=bool)
        rgb = arr[..., :3]

    pixels = rgb[mask]
    return pixels, mask, rgb


def _kmeans_colors(pixels: np.ndarray, k: int = 5, iters: int = 15) -> list[tuple[np.ndarray, float]]:
    """K-Means clustering in RGB/Lab space to find dominant color clusters and shares."""
    if len(pixels) == 0:
        return [(_hex_to_rgb("#808080") * 255, 1.0)]

    # Subsample if large
    if len(pixels) > 5000:
        idx = np.random.RandomState(42).choice(len(pixels), 5000, replace=False)
        sample = pixels[idx].astype(np.float64)
    else:
        sample = pixels.astype(np.float64)

    k = min(k, len(sample))
    rs = np.random.RandomState(42)
    centres = sample[rs.choice(len(sample), k, replace=False)]

    labels = np.zeros(len(sample), dtype=int)
    for _ in range(iters):
        # Euclidean distance in RGB
        dists = ((sample[:, None, :] - centres[None, :, :]) ** 2).sum(axis=-1)
        labels = dists.argmin(axis=1)
        for j in range(k):
            mask_j = labels == j
            if mask_j.any():
                centres[j] = sample[mask_j].mean(axis=0)

    # Calculate cluster shares
    counts = np.bincount(labels, minlength=k)
    total = float(len(sample))
    clusters = []
    for j in range(k):
        if counts[j] > 0:
            clusters.append((centres[j], counts[j] / total))

    clusters.sort(key=lambda x: -x[1])
    return clusters


def extract_garment_colors(img: Image.Image, max_colors: int = 4, merge_threshold: float = 10.0) -> list[dict]:
    """
    Extracts dominant color palette for a garment.
    Returns: [{"hex": "#...", "name": "...", "share": 0.xx}, ...]
    """
    pixels, _, _ = _extract_valid_pixels(img)
    if len(pixels) == 0:
        return [{"hex": "#808080", "name": "grey", "share": 1.0}]

    clusters = _kmeans_colors(pixels, k=6)

    # Convert to CIELAB and merge similar clusters
    entries = []
    for rgb, share in clusters:
        rgb_norm = np.clip(rgb / 255.0, 0, 1)
        lab = rgb2lab(rgb_norm.reshape(1, 1, 3))[0, 0]
        r, g, b = (rgb_norm * 255).astype(int)
        hex_code = f"#{r:02x}{g:02x}{b:02x}"
        entries.append({
            "lab": lab,
            "hex": hex_code,
            "name": get_nearest_color_name(hex_code),
            "share": float(share)
        })

    # Merge entries with ΔE < merge_threshold
    merged = []
    for e in entries:
        for m in merged:
            if deltaE_ciede2000(m["lab"].reshape(1, 3), e["lab"].reshape(1, 3))[0] < merge_threshold:
                tot = m["share"] + e["share"]
                m["lab"] = (m["lab"] * m["share"] + e["lab"] * e["share"]) / tot
                m["share"] = tot
                break
        else:
            merged.append(dict(e))

    merged.sort(key=lambda x: -x["share"])

    # Re-normalize shares
    tot_share = sum(m["share"] for m in merged)
    results = []
    for m in merged[:max_colors]:
        sh = round(m["share"] / tot_share, 3)
        if sh >= 0.05:
            # update hex from merged lab
            from skimage.color import lab2rgb
            rgb = np.clip(lab2rgb(m["lab"].reshape(1, 1, 3))[0, 0], 0, 1)
            r, g, b = (rgb * 255).astype(int)
            hex_code = f"#{r:02x}{g:02x}{b:02x}"
            results.append({
                "hex": hex_code,
                "name": get_nearest_color_name(hex_code),
                "share": sh
            })

    if not results:
        results = [entries[0]]

    return results


def detect_pattern(img: Image.Image) -> tuple[str, str]:
    """
    Analyzes spatial texture, color frequency, and gradients to classify:
    - Pattern: 'solid' | 'heather' | 'striped' | 'checkered' | 'plaid' | 'floral' | 'polka_dot' | 'graphic'
    - Scale: 'none' | 'fine' | 'medium' | 'bold'
    """
    pixels, mask, rgb = _extract_valid_pixels(img, max_dim=300)
    if len(pixels) == 0:
        return "solid", "none"

    colors = extract_garment_colors(img, max_colors=4)
    top_share = colors[0]["share"] if colors else 1.0
    num_distinct_colors = len([c for c in colors if c["share"] > 0.12])

    # Convert masked RGB to grayscale for frequency analysis
    gray = (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]).astype(np.float32)
    gray_pixels = gray[mask]

    std_dev = float(gray_pixels.std())
    
    # 1. Solid check: High dominant share and low luminance variance
    if top_share >= 0.85 and std_dev < 18.0:
        return "solid", "none"

    # 2. Gradient / Directional Analysis (Horizontal vs Vertical vs Diagonal)
    # Compute Sobel gradients
    sobel_h = ndimage.sobel(gray, axis=0)
    sobel_v = ndimage.sobel(gray, axis=1)

    mag_h = float(np.abs(sobel_h)[mask].mean())
    mag_v = float(np.abs(sobel_v)[mask].mean())
    ratio = (mag_h + 1e-4) / (mag_v + 1e-4)

    # 3. 2D Fast Fourier Transform on core patch
    ys, xs = np.where(mask)
    if len(ys) > 500:
        ymin, ymax = max(0, ys.min()), min(gray.shape[0], ys.max())
        xmin, xmax = max(0, xs.min()), min(gray.shape[1], xs.max())
        patch = gray[ymin:ymax, xmin:xmax]
        # Crop square sub-patch if possible
        min_side = min(patch.shape)
        if min_side > 64:
            c_y, c_x = patch.shape[0] // 2, patch.shape[1] // 2
            sub = patch[c_y - min_side//4 : c_y + min_side//4, c_x - min_side//4 : c_x + min_side//4]
            f_transform = np.fft.fft2(sub - sub.mean())
            f_shift = np.fft.fftshift(f_transform)
            magnitude = np.abs(f_shift)
            
            # Find peak frequencies
            cy, cx = magnitude.shape[0] // 2, magnitude.shape[1] // 2
            magnitude[cy-2:cy+3, cx-2:cx+3] = 0 # zero DC component
            peak_freq = np.unravel_index(magnitude.argmax(), magnitude.shape)
            peak_dist = np.hypot(peak_freq[0] - cy, peak_freq[1] - cx)
        else:
            peak_dist = 5.0
    else:
        peak_dist = 5.0

    # Scale estimation from dominant spatial frequency
    if peak_dist > 18:
        scale = "fine"
    elif peak_dist > 8:
        scale = "medium"
    else:
        scale = "bold"

    # 4. Pattern Classification Rules
    # Stripes: Strong anisotropy between horizontal and vertical gradients
    if (ratio > 1.85 or ratio < 0.54) and num_distinct_colors >= 2:
        return "striped", scale

    # Checkered / Plaid: Strong balanced gradients in both axes + multi-tone
    if num_distinct_colors >= 2 and std_dev > 24.0:
        if 0.75 <= ratio <= 1.35 and (mag_h > 15.0 and mag_v > 15.0):
            return "checkered" if num_distinct_colors == 2 else "plaid", scale

    # Heather: Micro-texture with high fine frequency but single color family
    if top_share >= 0.78 and scale == "fine" and std_dev < 28.0:
        return "heather", "fine"

    # Floral / Graphic: Multi-color with high variance and irregular distribution
    if num_distinct_colors >= 3:
        return "floral" if std_dev < 45.0 else "graphic", scale

    if num_distinct_colors == 2 and std_dev > 30.0:
        return "polka_dot" if scale in ("fine", "medium") else "graphic", scale

    if top_share >= 0.72:
        return "solid", "none"

    return "graphic", scale


def analyze_garment(img: Image.Image, category: str = "topwear", name: str = "Garment", item_id: str | int = 1) -> dict:
    """
    Full extraction for a single garment. Returns a structured dictionary
    matching the input schema required by outfit_color.py.
    """
    colors = extract_garment_colors(img)
    pattern, scale = detect_pattern(img)
    
    # Calculate pixel area of valid cutout
    if img.mode == "RGBA":
        alpha = np.array(img)[..., 3]
        area = int((alpha > 30).sum())
    else:
        area = img.width * img.height

    return {
        "id": item_id,
        "name": name,
        "category": category,
        "area": area,
        "colors": colors,
        "pattern": pattern,
        "scale": scale,
    }
