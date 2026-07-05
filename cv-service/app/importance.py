"""Per-pixel detail-importance map for spatially-varying segmentation. Phase 7.

Small high-frequency details (eyes, decorative text, stars, thin marks) get
merged into neighbors and quantized away, which is exactly what users notice
missing. This map marks where to *preserve* detail — high-contrast edges, the
main subject (rembg), and faces — and where to simplify (flat background). The
segment pipeline turns per-region mean importance into a per-region minimum
paintable area, so detail survives where it matters and the background collapses
into clean, large regions.

Everything fails soft: with no subject and no faces you still get a sensible
edge-driven map, and with matting disabled the whole thing reduces to edges.
"""

from __future__ import annotations

import cv2
import numpy as np

from . import config, faces, matte


def _edge_saliency(rgb: np.ndarray) -> np.ndarray:
    """Normalized [0,1] map of local contrast — high on edges/text/detail."""
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(gx, gy)

    # Widen thin edges into a small protected band, then smooth so importance is
    # a soft field (no hard seams that would themselves become region borders).
    k = max(3, int(min(rgb.shape[:2]) * config.IMPORTANCE_EDGE_DILATE_FRAC) | 1)
    mag = cv2.dilate(mag, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    mag = cv2.GaussianBlur(mag, (0, 0), max(1.0, k / 3.0))

    hi = float(np.percentile(mag, 98))  # robust max: ignore rare spikes
    if hi <= 1e-6:
        return np.zeros_like(mag)
    return np.clip(mag / hi, 0.0, 1.0)


def importance_map(rgb: np.ndarray) -> tuple[np.ndarray, dict]:
    """Build the importance field. Returns (importance HxW float32, meta)."""
    h, w = rgb.shape[:2]
    imp = np.full((h, w), config.IMPORTANCE_FLOOR, dtype=np.float32)
    meta = {"subject": False, "faces": 0}

    edges = _edge_saliency(rgb)
    imp += config.IMPORTANCE_W_EDGE * edges

    alpha = matte.subject_mask(rgb)
    if alpha is not None:
        imp += config.IMPORTANCE_W_SUBJECT * alpha
        # Outside the subject, damp edge saliency so a busy background doesn't
        # steal the detail budget from the subject.
        bg = 1.0 - alpha
        imp -= config.IMPORTANCE_BG_EDGE_DAMP * config.IMPORTANCE_W_EDGE * edges * bg
        np.maximum(imp, config.IMPORTANCE_FLOOR, out=imp)
        meta["subject"] = True

    boxes = faces.face_boxes(rgb)
    meta["faces"] = len(boxes)
    for (x, y, fw, fh) in boxes:
        pad = int(0.15 * max(fw, fh))
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(w, x + fw + pad), min(h, y + fh + pad)
        imp[y0:y1, x0:x1] += config.IMPORTANCE_FACE_BOOST

    return imp, meta
