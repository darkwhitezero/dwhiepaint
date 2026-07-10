"""Label map → SVG line art. Vector is the canonical printable output.

A raster line-art PNG is tied to a DPI; an SVG scales to any canvas size with
razor-clean lines. Each color's regions become one ``<path>`` (holes handled by
the even-odd fill rule), numbers are ``<text>`` placed at each component's pole
of inaccessibility. Contours are simplified with the same perimeter-relative +
absolute-px-capped epsilon as the raster renderer, so a thin region never
collapses into a self-intersecting outline.
"""

from __future__ import annotations

import cv2
import numpy as np
import svgwrite

from . import contours, numbering
from .cache import PaletteEntry


def _subpath(points: np.ndarray) -> str:
    if len(points) < 3:
        return ""
    d = f"M{points[0][0]:.1f},{points[0][1]:.1f}"
    d += "".join(f"L{x:.1f},{y:.1f}" for x, y in points[1:])
    return d + "Z"


def _region_path(mask: np.ndarray, importance_map: np.ndarray | None = None) -> str:
    """All contours (outer + holes) of a color mask as one even-odd path."""
    return "".join(
        _subpath(c) for c in contours.smoothed_contours(mask, importance_map=importance_map)
    )


def to_svg(
    label_img: np.ndarray,
    palette: list[PaletteEntry],
    *,
    min_label_radius: float = 6.0,
    stroke_px: float | None = None,
    importance_map: np.ndarray | None = None,
) -> str:
    """Return an SVG string: white regions, black outlines, region numbers."""
    h, w = label_img.shape
    stroke = stroke_px if stroke_px is not None else max(1.0, round(min(h, w) * 0.0012))
    number_scale = max(8.0, min(h, w) * 0.012)

    dwg = svgwrite.Drawing(size=(w, h))
    dwg.viewbox(0, 0, w, h)
    dwg.add(dwg.rect(insert=(0, 0), size=(w, h), fill="white"))

    outlines = dwg.g(fill="white", stroke="black", stroke_width=stroke,
                     stroke_linejoin="round")
    numbers = dwg.g(fill="black", font_family="sans-serif", text_anchor="middle")

    for entry in palette:
        mask = (label_img == entry.index - 1).astype(np.uint8)
        if not mask.any():
            continue

        path_d = _region_path(mask, importance_map=importance_map)
        if path_d:
            path = dwg.path(d=path_d, fill_rule="evenodd")
            # Per-color hooks so the UI can highlight one number's regions: a
            # stable class and the region's own colour as a CSS custom property.
            path["class"] = f"rg rg-{entry.index}"
            path["style"] = f"--rc:{entry.hex}"
            outlines.add(path)

        n, comp, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=4)
        for c in range(1, n):
            x, y, bw, bh, area = stats[c]
            if area < 16:
                continue
            crop = (comp[y:y + bh, x:x + bw] == c).astype(np.uint8)
            rx, ry, radius = numbering.interior_point(crop)
            if radius < min_label_radius:
                continue
            font_size = float(np.clip(radius * 0.9, number_scale * 0.7, number_scale * 3.0))
            numbers.add(dwg.text(
                str(entry.index),
                insert=(x + rx, y + ry + font_size * 0.35),
                font_size=font_size,
            ))

    dwg.add(outlines)
    dwg.add(numbers)
    return dwg.tostring()
