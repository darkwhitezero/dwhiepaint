"""Region contour extraction → simplify → smooth. Shared by the raster renderer
and the SVG vectorizer so both draw identical, smooth outlines.

Superpixel seams leave the region boundary with small superpixel-scale zig-zags
that are real features (above the approxPolyDP epsilon) yet read as ugly
staircases. approxPolyDP removes only sub-epsilon noise; Chaikin corner-cutting
then rounds the remaining hard corners into smooth, organic, paint-friendly
curves. Chaikin can't self-intersect a simple polygon (each cut stays inside its
corner), so it's safe on the thin regions that broke earlier smoothing attempts.
"""

from __future__ import annotations

import cv2
import numpy as np

from . import config


def _chaikin(pts: np.ndarray, iterations: int) -> np.ndarray:
    """Chaikin corner-cutting on a closed polygon (wraps last→first)."""
    for _ in range(iterations):
        if len(pts) < 3:
            return pts
        nxt = np.roll(pts, -1, axis=0)
        q = np.empty((len(pts) * 2, 2), dtype=np.float64)
        q[0::2] = 0.75 * pts + 0.25 * nxt
        q[1::2] = 0.25 * pts + 0.75 * nxt
        pts = q
    return pts


def smoothed_contours(mask: np.ndarray, iterations: int | None = None) -> list[np.ndarray]:
    """Return smoothed closed contours (float Nx2 arrays) of a binary mask.

    findContours (outer + holes) → approxPolyDP (drop sub-epsilon noise, epsilon
    perimeter-relative but absolutely px-capped) → Chaikin (round the rest).
    """
    iters = config.CONTOUR_SMOOTH_ITERS if iterations is None else iterations
    contours, _ = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    out: list[np.ndarray] = []
    for c in contours:
        if len(c) < 3:
            continue
        perimeter = cv2.arcLength(c, True)
        eps = min(config.CONTOUR_SIMPLIFY_EPS * perimeter, config.CONTOUR_SIMPLIFY_MAX_PX)
        simp = cv2.approxPolyDP(c, eps, True).reshape(-1, 2).astype(np.float64)
        if len(simp) >= 3:
            simp = _chaikin(simp, iters)
        out.append(simp)
    return out
