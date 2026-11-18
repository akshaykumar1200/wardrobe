"""Clean product pictures from Google Flow, through the flow-mcp app running on this laptop.

flow-mcp (github.com/GTAI-1/flow-mcp) drives Flow in its own signed-in Chrome window and serves a
local API on 127.0.0.1:8787. Images there cost 0 credits but take about 2-3 minutes each, so the
cut-out reply never waits for them: `start` runs the drawing in the background and the website
fetches it later by id (see routers/cutout.py).
"""

import asyncio
import io
import logging
import secrets
import time
from pathlib import Path

import httpx
from PIL import Image

from backend.config import settings

logger = logging.getLogger("wardrobe.flow")

DEADLINE_S = 15 * 60          # Flow works one picture at a time with 25-70 s pauses between them
KEEP_S = 60 * 60              # finished pictures wait this long for the website to collect them
TOKEN_FILE = Path.home() / ".flow-mcp" / "token"

# shortcut: in-memory, so pictures still drawing are lost if the service restarts; fine for one laptop.
_shots: dict[str, tuple[float, asyncio.Task]] = {}


def _prompt(name: str) -> str:
    return (
        f"Product photo of exactly the {name.lower()} in the reference image, on its own with no person: "
        "same colour, same fabric texture and wash, same seams, same print and logos, same fit. "
        "Laid flat on a clean pure white background, top-down flat lay, neatly smoothed, "
        "soft even studio lighting, subtle natural shadow, sharp focus, e-commerce catalog style."
    )


def _on_white(png: bytes) -> bytes:
    """The cut-out on white as a JPEG: only this garment is in the reference, never the person."""
    with Image.open(io.BytesIO(png)) as crop:
        rgba = crop.convert("RGBA")
    white = Image.new("RGB", rgba.size, (255, 255, 255))
    white.paste(rgba, mask=rgba.getchannel("A"))
    buf = io.BytesIO()
    white.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


async def _draw(png: bytes, name: str) -> bytes | None:
    """Asks flow-mcp for one picture. Returns PNG bytes, or None on any failure."""
    url = settings.FLOW_URL.rstrip("/")
    try:
        headers = {"x-flow-token": TOKEN_FILE.read_text(encoding="utf-8").strip()}
        async with httpx.AsyncClient(timeout=90) as client:
            up = await client.post(f"{url}/api/upload", params={"name": "garment.jpg"},
                                   content=_on_white(png), headers=headers)
            up.raise_for_status()
            scene = {"type": "image", "prompt": _prompt(name), "reference_images": [up.json()["path"]],
                     "aspect_ratio": "1:1", "max_credits": 0, "retries": 1}
            queued = await client.post(f"{url}/api/generate", headers=headers,
                                       json={"project": "Wardrobe", "scenes": [scene]})
            queued.raise_for_status()
            job_id = queued.json()["jobs"][0]["id"]

            deadline = time.monotonic() + DEADLINE_S
            while time.monotonic() < deadline:
                waited = await client.post(f"{url}/api/wait", headers=headers,
                                           json={"job_ids": [job_id], "timeout_seconds": 40})
                waited.raise_for_status()
                job = waited.json()["jobs"][0]
                if job["status"] == "done" and job.get("files"):
                    with Image.open(job["files"][0]) as drawn:
                        buf = io.BytesIO()
                        drawn.convert("RGB").save(buf, format="PNG")
                    return buf.getvalue()
                if job["status"] in ("done", "failed", "cancelled"):
                    logger.warning("flow picture for %s failed: %s", name, job.get("error"))
                    return None
            logger.warning("flow picture for %s took longer than %ss", name, DEADLINE_S)
    except Exception as exc:  # noqa: BLE001 - Flow is best-effort; the cut-out is already with the website
        logger.warning("flow picture for %s failed: %r", name, exc)
    return None


def start(png: bytes, name: str) -> str | None:
    """Starts drawing in the background and returns its id, or None when Flow is not set up."""
    if not settings.FLOW_URL:
        return None
    now = time.monotonic()
    for old in [k for k, (born, _) in _shots.items() if now - born > KEEP_S]:
        _shots.pop(old)[1].cancel()
    shot_id = secrets.token_hex(8)
    _shots[shot_id] = (now, asyncio.create_task(_draw(png, name)))
    return shot_id


def status(shot_id: str) -> tuple[str, bytes | None]:
    """("pending", None), ("ready", png), ("failed", None), or ("unknown", None)."""
    entry = _shots.get(shot_id)
    if entry is None:
        return "unknown", None
    task = entry[1]
    if not task.done():
        return "pending", None
    png = None if task.cancelled() else task.result()
    return ("ready", png) if png else ("failed", None)
