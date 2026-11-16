"""
Cloud-based Generative Flat-Lay service.
Transforms rough garment cutouts into symmetrical e-commerce catalogue product shots
using Google's Gemini Vision API (Interactions API / nano-banana).
"""

import base64
import logging
from typing import Optional
import httpx

from backend.config import settings

logger = logging.getLogger("wardrobe.flatlay")

GEMINI_INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"


async def generate_flatlay(
    crop_png_bytes: bytes,
    garment_name: str,
    color_hex: str,
    timeout_seconds: float = 12.0,
) -> Optional[bytes]:
    """
    Takes an extracted garment PNG and calls the Gemini API to reconstruct
    it as an e-commerce studio flat-lay. Returns None on failure or missing API key
    so the caller seamlessly falls back to the original cutout.
    """
    if not settings.FLATLAY_ENABLED or not settings.GEMINI_API_KEY:
        return None

    prompt = (
        f"Professional e-commerce studio flat-lay product photograph of this garment: "
        f"{garment_name} in {color_hex} color. Symmetrical lay-flat layout, laid completely flat "
        f"on a solid neutral black background. Sleeves spread evenly and symmetrically at 45 degrees. "
        f"Symmetrical neckline with inside back collar clearly visible and closed. "
        f"Maintain the exact fabric wash, marbled texture, and stitching. "
        f"No person, no body, no mannequin, no hanger, top-down catalog view."
    )

    payload = {
        "model": settings.FLATLAY_MODEL,
        "input": [
            {"type": "text", "text": prompt},
            {
                "type": "image",
                "mime_type": "image/png",
                "data": base64.b64encode(crop_png_bytes).decode("ascii"),
            },
        ],
    }

    headers = {
        "x-goog-api-key": settings.GEMINI_API_KEY,
        "Content-Type": "application/json",
        "Api-Revision": "2026-05-20",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.post(
                GEMINI_INTERACTIONS_URL,
                json=payload,
                headers=headers,
            )
            if resp.status_code != 200:
                logger.warning(
                    f"Flat-lay generation response {resp.status_code}: {resp.text[:200]}"
                )
                return None

            data = resp.json()
            output_image = data.get("output_image") or {}
            img_b64 = output_image.get("data")
            if not img_b64:
                # Step-based fallback for complex interaction structures
                for step in data.get("steps", []):
                    if step.get("output_image", {}).get("data"):
                        img_b64 = step["output_image"]["data"]
                        break

            if img_b64:
                return base64.b64decode(img_b64)
            return None

    except Exception as exc:
        logger.warning(f"Flat-lay request encountered error: {exc}. Falling back to cutout.")
        return None
