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
    # A real subject means BOTH a mask exists AND rembg was actually confident
    # about something — on a real landscape photo (verified: docs/issues/
    # landscape-quality's daisy-field test image) rembg almost always returns
    # a non-None mask even with no coherent foreground object, but that mask
    # is then essentially all-zero (mean << 1%) rather than actually None. An
    # `alpha is not None` check alone missed this and never applied the
    # no-subject damping below on exactly the images it exists for.
    has_subject = alpha is not None and float(alpha.mean()) >= config.IMPORTANCE_SUBJECT_MIN_MEAN
    if has_subject:
        imp += config.IMPORTANCE_W_SUBJECT * alpha
        # Outside the subject, damp edge saliency so a busy background doesn't
        # steal the detail budget from the subject.
        bg = 1.0 - alpha
        imp -= config.IMPORTANCE_BG_EDGE_DAMP * config.IMPORTANCE_W_EDGE * edges * bg
        np.maximum(imp, config.IMPORTANCE_FLOOR, out=imp)
        meta["subject"] = True
    else:
        # No real subject (rembg found nothing confident, or matting didn't
        # run at all — typically a landscape/scene with no single foreground
        # object). The subject-relative damp above never runs in this branch,
        # so on a subjectless image whose texture is uniformly high-contrast
        # (a flower field, foliage, water ripples) the WHOLE frame reads as
        # "important" and the per-region min-area collapses to the detail
        # floor everywhere — hundreds of unpaintable micro-regions survive the
        # merge (docs/issues/landscape-quality, Problem 1). Apply the same
        # kind of damping globally instead: it's the natural degenerate case
        # of "outside the subject" when there is no subject, so no separate
        # subject-vs-background split is needed.
        imp -= config.IMPORTANCE_NO_SUBJECT_EDGE_DAMP * config.IMPORTANCE_W_EDGE * edges
        np.maximum(imp, config.IMPORTANCE_FLOOR, out=imp)

    boxes = faces.face_boxes(rgb)
    meta["faces"] = len(boxes)
    for (x, y, fw, fh) in boxes:
        pad = int(0.15 * max(fw, fh))
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(w, x + fw + pad), min(h, y + fh + pad)
        imp[y0:y1, x0:x1] += config.IMPORTANCE_FACE_BOOST

    return imp, meta
