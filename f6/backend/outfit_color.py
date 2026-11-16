"""
outfit_color.py

Whole-outfit palette signature (Problem 2) and outfit harmony scoring engine (Problem 3).
"""

import numpy as np
from skimage.color import deltaE_ciede2000

from backend.colors import PALETTE, _hex_to_lab

NEUTRALS = {
    "black", "charcoal", "grey", "light grey", "silver", "white",
    "off-white", "cream", "ivory", "beige", "sand", "taupe", "camel",
    "tan", "brown", "chocolate", "khaki", "navy", "midnight", "denim",
    "olive",
}

NEUTRAL_CHROMA = 16.0


def _lab(hex_code: str) -> np.ndarray:
    return _hex_to_lab(hex_code)


def _chroma(lab: np.ndarray) -> float:
    return float(np.sqrt(lab[1] ** 2 + lab[2] ** 2))


def _hue(lab: np.ndarray) -> float:
    return float(np.degrees(np.arctan2(lab[2], lab[1])) % 360)


def _hue_gap(h1: float, h2: float) -> float:
    d = abs(h1 - h2) % 360
    return min(d, 360 - d)


def is_neutral(color: dict) -> bool:
    if color.get("name") in NEUTRALS:
        return True
    return _chroma(_lab(color["hex"])) < NEUTRAL_CHROMA


def outfit_palette(items, merge_threshold: float = 12.0):
    if not items:
        return None

    total_area = sum(max(i.get("area", 1), 1) for i in items)

    entries = []
    for it in items:
        w_item = (max(it.get("area", 1), 1) / total_area) ** 0.75
        for c in it.get("colors", []):
            entries.append({
                "lab": _lab(c["hex"]),
                "name": c.get("name"),
                "weight": w_item * c.get("share", 1.0),
            })

    if not entries:
        return None

    norm = sum(e["weight"] for e in entries)
    for e in entries:
        e["weight"] /= norm

    merged = []
    for e in sorted(entries, key=lambda x: -x["weight"]):
        for m in merged:
            if deltaE_ciede2000(m["lab"].reshape(1, 3),
                                e["lab"].reshape(1, 3))[0] < merge_threshold:
                tot = m["weight"] + e["weight"]
                m["lab"] = (m["lab"] * m["weight"] + e["lab"] * e["weight"]) / tot
                m["weight"] = tot
                break
        else:
            merged.append(dict(e))

    merged.sort(key=lambda x: -x["weight"])

    def to_hex(lab):
        from skimage.color import lab2rgb
        rgb = np.clip(lab2rgb(lab.reshape(1, 1, 3))[0, 0], 0, 1)
        r, g, b = (rgb * 255).astype(int)
        return f"#{r:02x}{g:02x}{b:02x}"

    def nearest_name(lab):
        names = list(PALETTE.keys())
        pal = np.array([_hex_to_lab(v) for v in PALETTE.values()])
        d = deltaE_ciede2000(pal, np.tile(lab.reshape(1, 3), (len(pal), 1)))
        return names[int(np.argmin(d))]

    palette = [{
        "hex": to_hex(m["lab"]),
        "name": nearest_name(m["lab"]),
        "share": round(float(m["weight"]), 3),
    } for m in merged if m["weight"] >= 0.04]

    neutral_share = sum(p["share"] for p in palette if is_neutral(p))
    accents = [p for p in palette if not is_neutral(p)]

    lightness = [_lab(p["hex"])[0] for p in palette]
    spread = max(lightness) - min(lightness) if len(lightness) > 1 else 0.0
    warmth = sum(_lab(p["hex"])[2] * p["share"] for p in palette)

    return {
        "palette": palette[:5],
        "dominant": palette[0] if palette else None,
        "accent": accents[0] if accents else None,
        "neutral_share": round(neutral_share, 2),
        "contrast": ("high" if spread > 55 else
                     "medium" if spread > 25 else "low"),
        "temperature": ("warm" if warmth > 8 else
                        "cool" if warmth < -4 else "neutral"),
        "n_accent_colors": len(accents),
    }


def _relationship(a: dict, b: dict) -> tuple[str, float]:
    la, lb = _lab(a["hex"]), _lab(b["hex"])
    ha, hb = _hue(la), _hue(lb)
    gap = _hue_gap(ha, hb)
    ca, cb = _chroma(la), _chroma(lb)
    dL = abs(la[0] - lb[0])

    if gap < 18:
        return ("monochrome", 0.85 if dL > 22 else 0.45)
    if gap < 45:
        return ("analogous", 0.80)
    if 150 <= gap <= 210:
        muted = min(ca, cb) < 38
        return ("complementary", 0.75 if muted else 0.55)
    if 100 <= gap < 150 or 210 < gap <= 260:
        return ("triadic", 0.65)

    both_loud = min(ca, cb) > 40
    return ("clash", 0.30 if both_loud else 0.50)


def score_outfit(items):
    if len(items) < 2:
        return None

    sig = outfit_palette(items)
    if not sig:
        return None

    score = 70.0
    notes = []
    accents = [p for p in sig["palette"] if not is_neutral(p)]

    # 1. Accent count
    if len(accents) == 0:
        score += 12
        notes.append("All-neutral palette. Safe, polished, and hard to get wrong.")
    elif len(accents) == 1:
        score += 15
        notes.append(f"Neutral base with one {accents[0]['name']} accent. The most reliable sartorial structure.")
    elif len(accents) == 2:
        rel, rel_score = _relationship(accents[0], accents[1])
        score += (rel_score - 0.5) * 40
        if rel == "clash":
            notes.append(f"{accents[0]['name']} and {accents[1]['name']} sit in an awkward color zone.")
        else:
            notes.append(f"{accents[0]['name']} and {accents[1]['name']} form a {rel} harmony.")
    else:
        score -= 18
        notes.append(f"{len(accents)} competing loud colors. Consider dropping one to a neutral.")

    # 2. Contrast
    if sig["contrast"] == "low" and len(accents) < 2:
        score -= 10
        notes.append("Everything sits at a similar lightness, so the outfit reads flat. Swap one piece lighter or darker.")
    elif sig["contrast"] == "high":
        score += 6

    # 3. Temperature
    temps = []
    for p in sig["palette"]:
        if is_neutral(p):
            continue
        b = _lab(p["hex"])[2]
        temps.append("warm" if b > 8 else "cool" if b < -4 else "neutral")
    if "warm" in temps and "cool" in temps:
        score -= 6
        notes.append("Mixing warm and cool accents. Needs neutral anchors to carry the look.")

    # 4. Pattern mixing
    patterned = [i for i in items if i.get("pattern") not in (None, "solid", "heather")]
    if len(patterned) >= 2:
        scales = {i.get("scale") for i in patterned}
        if len(scales) == 1:
            score -= 14
            notes.append("Two patterns at the same scale will fight. Pair a bold pattern with a fine one instead.")
        else:
            score += 4
            notes.append("Two patterns at different scales, which is balanced.")
    if len(patterned) >= 3:
        score -= 12
        notes.append("Three patterns is busy. Ground with a solid piece.")

    # 5. Shoes
    shoes = [i for i in items if i.get("category") == "shoes"]
    if shoes and shoes[0].get("colors"):
        sc = shoes[0]["colors"][0]
        if is_neutral(sc):
            score += 5
        else:
            match = any(
                deltaE_ciede2000(_lab(sc["hex"]).reshape(1, 3),
                                 _lab(p["hex"]).reshape(1, 3))[0] < 20
                for p in sig["palette"][:3])
            if match:
                score += 8
                notes.append(f"The {sc['name']} shoes pick up a color already in the outfit.")
            else:
                score -= 8
                notes.append(f"The {sc['name']} shoes introduce an unrepeated tone.")

    score = float(np.clip(score, 0, 100))
    verdict = ("strong" if score >= 78 else
               "solid" if score >= 62 else
               "workable" if score >= 45 else "off")

    return {
        "score": round(score),
        "verdict": verdict,
        "notes": notes,
        "palette": sig,
    }


def rank_combinations(wardrobe, top_n: int = 12):
    from itertools import product

    tops = [i for i in wardrobe if i.get("category") == "topwear"]
    bottoms = [i for i in wardrobe if i.get("category") == "bottomwear"]
    shoes = [i for i in wardrobe if i.get("category") == "shoes"] or [None]

    results = []
    for t, b, s in product(tops, bottoms, shoes):
        combo = [t, b] + ([s] if s else [])
        r = score_outfit(combo)
        if r:
            # Variety factor based on wear_count
            total_wears = sum(i.get("wear_count", 0) for i in combo)
            adjusted_score = max(0, r["score"] - min(15, total_wears * 2))
            results.append({
                "items": combo,
                "adjusted_score": round(adjusted_score),
                **r
            })

    results.sort(key=lambda x: -x["score"])
    return results[:top_n]
