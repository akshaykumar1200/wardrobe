"""Class-agnostic subject matting.

The clothes model only understands people. It has no notion of "object versus
background", which is why a pair of sneakers on a bed came back as
"upper-clothes" at 0.66 confidence, and why the hand-written colour heuristic
that replaced it bit chunks out of pale suede -- on a shaded bed, a shoe pixel
and a bed pixel are genuinely the same RGB, so no threshold can separate them.

BiRefNet is trained for exactly that separation and returns a real fractional
alpha, so it does not need the colours to differ.

Loading is lazy and every failure is non-fatal: if the weights are missing or
the machine is offline, callers fall back to the colour heuristic.
"""
import logging
import threading

import numpy as np
import torch
from PIL import Image

from backend.config import settings

log = logging.getLogger(__name__)

_model = None
_load_failed = False
_lock = threading.Lock()

_MEAN = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
_STD = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)


def _load():
    global _model, _load_failed
    if _model is not None or _load_failed:
        return _model

    with _lock:
        if _model is not None or _load_failed:
            return _model
        try:
            from transformers import AutoModelForImageSegmentation
            model = AutoModelForImageSegmentation.from_pretrained(
                settings.MATTING_MODEL_ID, trust_remote_code=True
            )
            model.eval()
            _model = model
            log.info("matting model %s loaded", settings.MATTING_MODEL_ID)
        except Exception:
            # Offline, weights absent, or an incompatible torch build. The
            # colour path still works, so this must never take the server down.
            _load_failed = True
            log.warning("matting model unavailable; falling back to colour heuristic",
                        exc_info=True)
    return _model


def available() -> bool:
    return settings.MATTING_ENABLED and _load() is not None


def subject_matte(img: Image.Image) -> np.ndarray | None:
    """Soft 0..1 alpha for the photo's main subject, at `img` resolution.

    Returns None when matting is disabled or the model could not be loaded.
    """
    if not settings.MATTING_ENABLED:
        return None

    model = _load()
    if model is None:
        return None

    side = settings.MATTING_SIDE
    try:
        small = img.convert("RGB").resize((side, side), Image.BILINEAR)
        x = torch.from_numpy(np.asarray(small).copy()).permute(2, 0, 1).float() / 255.0
        x = ((x - _MEAN) / _STD).unsqueeze(0)

        with torch.no_grad():
            pred = model(x)[-1].sigmoid()[0, 0]

        matte = torch.nn.functional.interpolate(
            pred[None, None], size=(img.height, img.width),
            mode="bilinear", align_corners=False,
        )[0, 0]
        return matte.clamp(0, 1).numpy()
    except Exception:
        log.warning("matting failed for one image; using colour heuristic", exc_info=True)
        return None
