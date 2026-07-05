"""Subject/background matting via rembg (u2net). Phase 7.

Produces a soft alpha mask of the main subject so segmentation can spend its
detail budget where it matters — keep the subject crisp, simplify the
background. Fails soft: if rembg/onnxruntime is unavailable, the model is
missing, or the image is too small to bother, returns None and the caller
falls back to uniform detail. The rembg session is created once and reused.
"""

from __future__ import annotations

import cv2
import numpy as np

from . import config

_session = None
_session_failed = False


def _get_session():
    """Lazily create (and cache) the rembg session; None if unavailable."""
    global _session, _session_failed
    if _session is not None or _session_failed:
        return _session
    try:
        from rembg import new_session

        _session = new_session(config.REMBG_MODEL)
    except Exception:  # noqa: BLE001 — matting is optional; degrade gracefully
        _session_failed = True
        _session = None
    return _session


def subject_mask(rgb: np.ndarray) -> np.ndarray | None:
    """Return a soft [0,1] HxW subject alpha, or None on opt-out/failure."""
    if not config.SUBJECT_AWARE:
        return None
    h, w = rgb.shape[:2]
    if min(h, w) < config.SUBJECT_MIN_SIDE:
        return None

    session = _get_session()
    if session is None:
        return None

    # u2net downsamples to 320px internally, so running it on the full working
    # image just makes rembg's full-res mask upscale + post-process needlessly
    # slow. Infer on a ≤REMBG_MAX_SIDE copy and upscale the soft mask back.
    longest = max(h, w)
    if longest > config.REMBG_MAX_SIDE:
        s = config.REMBG_MAX_SIDE / longest
        small = cv2.resize(rgb, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA)
    else:
        small = rgb

    try:
        from rembg import remove

        out = remove(small, session=session, only_mask=True, post_process_mask=True)
    except Exception:  # noqa: BLE001 — any inference failure → no mask
        return None

    alpha = np.asarray(out)
    if alpha.ndim == 3:
        alpha = alpha[..., 0]
    if alpha.shape[:2] != (h, w):
        alpha = cv2.resize(alpha, (w, h), interpolation=cv2.INTER_LINEAR)
    return alpha.astype(np.float32) / 255.0
