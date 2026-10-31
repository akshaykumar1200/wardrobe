"""Adapt wardrobe item rows to the colour scorer's input format."""

from contextvars import ContextVar
from functools import lru_cache
import io
import sys

from PIL import Image

from backend.colors import get_nearest_color_name
from backend.database import SessionLocal
from backend import crops
from backend.config import settings
from backend.models import Item

# pattern.py still imports ``colors`` as a top-level module. Keep that legacy
# import resolvable while importing it as part of the backend package.
import backend.colors as _colors
sys.modules.setdefault("colors", _colors)
from backend.pattern import analyze_garment


_analysis_context: ContextVar[tuple[bytes, str, str, int]] = ContextVar("analysis_context")

_MANUAL_AREAS = {
    "topwear": 70000,
    "bottomwear": 65000,
    "shoes": 13000,
    "accessories": 5000,
    "other": 20000,
}


@lru_cache(maxsize=512)
def _cached_visual_fields(stored_name: str) -> tuple[list[dict], str, str, int]:
    """Cache extraction by content-addressed filename; metadata is attached per call."""
    data, category, name, item_id = _analysis_context.get()
    with Image.open(io.BytesIO(data)) as image:
        result = analyze_garment(image, category, name, item_id)
    # shortcut: pattern detection is discarded, revisit if detect_pattern is retuned
    # on photo crops. On real garments it called a plain green t-shirt "graphic
    # bold" and grey trainers "plaid" -- fabric texture, folds and shading read as
    # pattern -- and those false positives cost a normal outfit ~30 points. A wrong
    # pattern is worse than no pattern, so claim "solid" and score on colour, which
    # is what PRD 14 says the ranking is based on anyway.
    return result["colors"], "solid", "none", result["area"]


def describe(item: Item) -> dict | None:
    """Return scorer input for an item, or None when it has no scoreable data."""
    data = None
    if item.stored_name:
        db = SessionLocal()
        try:
            data = crops.get(db, item.user_id, item.stored_name)
        finally:
            db.close()

    if data is not None:
        token = _analysis_context.set((data, item.category, item.name, item.id))
        try:
            colors, pattern, scale, area = _cached_visual_fields(item.stored_name)
        finally:
            _analysis_context.reset(token)
    elif item.color:
        # shortcut: fixed areas for photo-less garments, real pixel area when a crop exists
        colors = [{
            "hex": item.color,
            "name": get_nearest_color_name(item.color),
            "share": 1.0,
        }]
        pattern, scale = "solid", "none"
        area = _MANUAL_AREAS.get(item.category, _MANUAL_AREAS["other"])
    else:
        return None

    return {
        "id": item.id,
        "name": item.name,
        "category": item.category,
        "colors": colors,
        "pattern": pattern,
        "scale": scale,
        "area": area,
    }
