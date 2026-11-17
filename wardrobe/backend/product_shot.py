"""Product-style picture of a top, drawn by TryOffDiff in its own Python environment.

TryOffDiff needs newer torch/diffusers than this service pins, so it runs as a
separate process (tryoff/run_tryoff.py) and this module only starts it, waits,
and repaints its output with the garment's real colours. Off unless
TRYOFF_PYTHON is set, and every failure returns None so the caller keeps the
real cut-out.
"""

import os
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

from backend.config import settings

SCRIPT = Path(__file__).resolve().parents[1] / "tryoff" / "run_tryoff.py"
STEPS, SEED = 30, 42
# The website gives the whole request 90 s; past this the cut-out is sent instead.
DEADLINE_S = 70


class ProductShot:
    """One TryOffDiff run. Started before the cut-out so both work at the same time."""

    def __init__(self, photo: Image.Image):
        self._started = time.monotonic()
        self._tmp = tempfile.TemporaryDirectory()
        self._dir = Path(self._tmp.name)
        photo.convert("RGB").save(self._dir / "in.jpg", quality=95)
        self._log = open(self._dir / "log.txt", "w")
        # Plain file names + cwd: the script splits its argument on ":", which a C:\ path breaks.
        # shortcut: loads the model on every upload (~15 s on a GPU); keep a warm worker if uploads get frequent.
        self._proc = subprocess.Popen(
            [settings.TRYOFF_PYTHON, str(SCRIPT), str(STEPS), str(SEED), "in.jpg:out.png"],
            cwd=self._dir, stdout=self._log, stderr=subprocess.STDOUT,
            env={**os.environ, "HF_HUB_OFFLINE": "1"},  # models are fetched once by hand, never mid-upload
        )

    def result(self) -> Image.Image | None:
        """Blocks until the picture is ready or the deadline passes."""
        try:
            code = self._proc.wait(max(1.0, DEADLINE_S - (time.monotonic() - self._started)))
            if code != 0:
                raise RuntimeError(f"exit code {code}")
            with Image.open(self._dir / "out.png") as img:
                return img.convert("RGB")
        except Exception as exc:
            self._log.flush()
            tail = (self._dir / "log.txt").read_text(errors="replace")[-600:]
            print(f"product shot failed ({exc!r}), keeping the cut-out. Last output:\n{tail}", flush=True)
            return None
        finally:
            self.close()

    def close(self):
        if self._proc.poll() is None:
            self._proc.kill()
            self._proc.wait()
        self._log.close()
        self._tmp.cleanup()


def start(photo: Image.Image) -> ProductShot | None:
    if not settings.TRYOFF_PYTHON:
        return None
    try:
        return ProductShot(photo)
    except Exception as exc:
        print(f"product shot could not start ({exc!r}), keeping the cut-out", flush=True)
        return None


def _largest(mask: np.ndarray) -> np.ndarray:
    labels, n = ndimage.label(mask)
    if n == 0:
        return mask
    sizes = ndimage.sum(mask, labels, range(1, n + 1))
    return labels == (int(np.argmax(sizes)) + 1)


def recolour(generated: Image.Image, cutout: Image.Image) -> Image.Image | None:
    """Repaint the drawn garment with the real cut-out's colours, on a transparent background.

    TryOffDiff gets the shape right but the colour too bright; each Lab channel of
    the drawing is quantile-mapped onto the real garment's pixels.
    """
    from skimage.color import lab2rgb, rgb2lab

    real = np.asarray(cutout.convert("RGBA"))
    # Edge pixels blend into skin and background; sample the inside of the garment.
    inside = ndimage.binary_erosion(real[..., 3] > 200, iterations=3)
    if inside.sum() < 50:
        inside = real[..., 3] > 200
    if inside.sum() < 50:
        return None
    ref = rgb2lab(real[..., :3][inside].reshape(-1, 1, 3) / 255.0).reshape(-1, 3)

    arr = np.asarray(generated.convert("RGB"))
    border = np.concatenate([arr[:8].reshape(-1, 3), arr[-8:].reshape(-1, 3),
                             arr[:, :8].reshape(-1, 3), arr[:, -8:].reshape(-1, 3)])
    distance = np.linalg.norm(arr.astype(np.float32) - np.median(border, axis=0), axis=2)
    mask = _largest(ndimage.binary_fill_holes(distance > 30))
    # A drawing that is nearly empty or fills the frame is not a garment on a plain background.
    if not 0.05 < mask.mean() < 0.95:
        return None

    lab = rgb2lab(arr[mask].reshape(-1, 1, 3) / 255.0).reshape(-1, 3)
    fixed = np.empty_like(lab)
    for c in range(3):
        rank = np.argsort(np.argsort(lab[:, c])) / max(len(lab) - 1, 1)
        fixed[:, c] = np.quantile(ref[:, c], rank)
    out = np.zeros((*arr.shape[:2], 4), np.uint8)
    out[..., :3] = arr
    out[..., :3][mask] = (np.clip(lab2rgb(fixed.reshape(-1, 1, 3)).reshape(-1, 3), 0, 1) * 255).round()
    out[..., 3] = (np.clip(ndimage.gaussian_filter(mask.astype(np.float32), 1) * 2 - 0.5, 0, 1) * 255).round()

    ys, xs = np.nonzero(out[..., 3])
    return Image.fromarray(out).crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
