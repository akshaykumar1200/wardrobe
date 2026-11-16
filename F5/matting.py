"""
matting.py for f5

BiRefNet class-agnostic subject matting.
"""

import logging
import threading
import numpy as np
import torch
from PIL import Image

log = logging.getLogger(__name__)

MATTING_ENABLED = True
MATTING_MODEL_ID = "ZhengPeng7/BiRefNet"
MATTING_SIDE = 512

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
                MATTING_MODEL_ID, trust_remote_code=True
            )
            model.eval()
            _model = model
            log.info("matting model %s loaded", MATTING_MODEL_ID)
        except Exception:
            _load_failed = True
            log.warning("matting model unavailable; falling back to colour heuristic", exc_info=True)
    return _model


def subject_matte(img: Image.Image) -> np.ndarray | None:
    if not MATTING_ENABLED:
        return None

    model = _load()
    if model is None:
        return None

    side = MATTING_SIDE
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
