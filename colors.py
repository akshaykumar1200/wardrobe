"""
colors.py

Core color utilities and palette definitions for fashion items and outfit scoring.
"""

import numpy as np
from skimage.color import rgb2lab, deltaE_ciede2000

# Canonical fashion color palette mapping named colors to representative hex codes
PALETTE = {
    # Neutrals
    "black": "#111111",
    "charcoal": "#333333",
    "grey": "#808080",
    "light grey": "#D3D3D3",
    "silver": "#C0C0C0",
    "white": "#FFFFFF",
    "off-white": "#F8F8F6",
    "cream": "#FFFDD0",
    "ivory": "#FFFFF0",
    "beige": "#F5F5DC",
    "sand": "#C2B280",
    "taupe": "#483C32",
    "camel": "#C19A6B",
    "tan": "#D2B48C",
    "brown": "#8B4513",
    "chocolate": "#3D2314",
    "khaki": "#F0E68C",
    "navy": "#000080",
    "midnight": "#191970",
    "denim": "#2B4C7E",
    "olive": "#556B2F",

    # Greens
    "forest green": "#228B22",
    "sage": "#9CB071",
    "emerald": "#50C878",
    "mint": "#98FF98",
    "pine": "#01796F",

    # Blues
    "royal blue": "#4169E1",
    "sky blue": "#87CEEB",
    "cobalt": "#0047AB",
    "teal": "#008080",
    "cyan": "#00FFFF",

    # Reds & Pinks
    "red": "#FF0000",
    "ruby": "#E0115F",
    "burgundy": "#800020",
    "crimson": "#DC143C",
    "rose": "#FF007F",
    "pink": "#FFC0CB",
    "blush": "#DE5D83",
    "coral": "#FF7F50",

    # Yellows & Oranges
    "yellow": "#FFFF00",
    "mustard": "#FFDB58",
    "gold": "#FFD700",
    "amber": "#FFBF00",
    "orange": "#FFA500",
    "terracotta": "#E2725B",
    "rust": "#B7410E",

    # Purples
    "purple": "#800080",
    "violet": "#7F00FF",
    "plum": "#8E4585",
    "lavender": "#E6E6FA",
    "lilac": "#C8A2C8",
    "magenta": "#FF00FF",
}


def _hex_to_rgb(hex_code: str) -> np.ndarray:
    """Convert hex string (e.g. '#2c524a') to normalized float RGB in [0, 1]."""
    h = hex_code.lstrip("#")
    if len(h) == 3:
        h = "".join([c * 2 for c in h])
    r, g, b = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    return np.array([r, g, b], dtype=np.float32) / 255.0


def _hex_to_lab(hex_code: str) -> np.ndarray:
    """Convert hex code to CIELAB space."""
    rgb = _hex_to_rgb(hex_code)
    # rgb2lab expects shape (M, N, 3) or (1, 1, 3)
    lab = rgb2lab(rgb.reshape(1, 1, 3))
    return lab[0, 0]


def get_nearest_color_name(hex_code: str) -> str:
    """Find the closest human-readable fashion color name using CIEDE2000 distance."""
    target_lab = _hex_to_lab(hex_code)
    names = list(PALETTE.keys())
    pal_labs = np.array([_hex_to_lab(v) for v in PALETTE.values()])
    distances = deltaE_ciede2000(pal_labs, np.tile(target_lab.reshape(1, 3), (len(pal_labs), 1)))
    return names[int(np.argmin(distances))]
