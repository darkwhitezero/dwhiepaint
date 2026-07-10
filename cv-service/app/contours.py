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


def _contour_eps_frac(contour: np.ndarray, importance_map: np.ndarray | None) -> float:
    """Perimeter-relative epsilon fraction for one contour: small (detail-
    preserving) where the contour sits in an important region (subject/edges/
    faces), large (current, coarser) in flat background. Falls back to the
    uniform ``CONTOUR_SIMPLIFY_EPS`` when no map is given, so behavior is
    byte-identical to before this existed.
    """
    if importance_map is None:
        return config.CONTOUR_SIMPLIFY_EPS
    m = cv2.moments(contour)
    if m["m00"]:
        cx, cy = m["m10"] / m["m00"], m["m01"] / m["m00"]
    else:
        cx, cy = contour[:, 0, 0].mean(), contour[:, 0, 1].mean()
    h, w = importance_map.shape
    px = int(np.clip(cx, 0, w - 1))
    py = int(np.clip(cy, 0, h - 1))
    imp = float(importance_map[py, px])

    span = max(1e-6, config.IMPORTANCE_HIGH - config.IMPORTANCE_LOW)
    t = np.clip((imp - config.IMPORTANCE_LOW) / span, 0.0, 1.0)
    # t=0 (background) -> current EPS; t=1 (important) -> the finer DETAIL eps.
    return config.CONTOUR_SIMPLIFY_EPS - t * (
        config.CONTOUR_SIMPLIFY_EPS - config.CONTOUR_SIMPLIFY_EPS_DETAIL
    )


def smoothed_contours(
    mask: np.ndarray,
    iterations: int | None = None,
    importance_map: np.ndarray | None = None,
) -> list[np.ndarray]:
    """Return smoothed closed contours (float Nx2 arrays) of a binary mask.

    findContours (outer + holes) → approxPolyDP (drop sub-epsilon noise, epsilon
    perimeter-relative but absolutely px-capped) → Chaikin (round the rest).

    ``importance_map`` (optional, full-image HxW float array) lets epsilon vary
    PER CONTOUR: a single color's mask can span several disjoint physical blobs
    of very different importance, so the epsilon decision is made per extracted
    contour (after findContours, before approxPolyDP), not once for the whole
    mask. The absolute pixel cap (``CONTOUR_SIMPLIFY_MAX_PX``) still applies
    unconditionally to every contour regardless of importance — it is the
    self-intersection guard and must never be relaxed.
    """
    iters = config.CONTOUR_SMOOTH_ITERS if iterations is None else iterations
    contours, _ = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    out: list[np.ndarray] = []
    for c in contours:
        if len(c) < 3:
            continue
        perimeter = cv2.arcLength(c, True)
        eps_frac = _contour_eps_frac(c, importance_map)
        eps = min(eps_frac * perimeter, config.CONTOUR_SIMPLIFY_MAX_PX)
        simp = cv2.approxPolyDP(c, eps, True).reshape(-1, 2).astype(np.float64)
        if len(simp) >= 3:
            simp = _chaikin(simp, iters)
        out.append(simp)
    return out
