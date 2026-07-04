"""Where to place a region's number: the pole of inaccessibility.

The best point for a label is the interior point farthest from every edge —
the "pole of inaccessibility" (the centre of the largest inscribed circle),
NOT the centroid, which for a C- or crescent-shaped region can land outside it.

We build a shapely polygon from the region's contour *including its holes* and
call ``shapely.ops.polylabel`` for a sub-pixel-accurate pole. A distance-
transform argmax fallback (also inscribed-circle-based and hole-aware) covers
any degenerate contour shapely can't build.
"""

from __future__ import annotations

import cv2
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import polylabel


def _dt_fallback(mask: np.ndarray) -> tuple[float, float, float]:
    """Inscribed-circle centre via distance transform → (x, y, radius)."""
    dt = cv2.distanceTransform(mask, cv2.DIST_L2, 3)
    radius = float(dt.max())
    ry, rx = np.unravel_index(int(np.argmax(dt)), dt.shape)
    return float(rx), float(ry), radius


def interior_point(mask: np.ndarray) -> tuple[float, float, float]:
    """Return (x, y, radius) of the pole of inaccessibility of a binary mask.

    radius is the distance from that point to the nearest boundary (outer edge
    or a hole), i.e. the largest number that can sit there without touching a line.
    """
    contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return _dt_fallback(mask)

    hier = hierarchy[0] if hierarchy is not None else [[-1, -1, -1, -1]] * len(contours)
    outer = [i for i, h in enumerate(hier) if h[3] == -1] or list(range(len(contours)))
    best = max(outer, key=lambda i: cv2.contourArea(contours[i]))

    ext = contours[best][:, 0, :]
    if len(ext) < 4:
        return _dt_fallback(mask)

    holes = [
        contours[i][:, 0, :]
        for i, h in enumerate(hier)
        if h[3] == best and len(contours[i]) >= 4
    ]
    try:
        poly = Polygon(ext, holes)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty:
            return _dt_fallback(mask)
        if poly.geom_type == "MultiPolygon":
            poly = max(poly.geoms, key=lambda g: g.area)
        pt = polylabel(poly, tolerance=1.0)
        radius = float(poly.boundary.distance(pt))
        return float(pt.x), float(pt.y), radius
    except Exception:  # noqa: BLE001 — any geometry failure → robust raster fallback
        return _dt_fallback(mask)
