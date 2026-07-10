"""Rendering helpers: region outlines and region numbers on a white canvas."""

from __future__ import annotations

import cv2
import numpy as np

from . import contours, numbering
from .cache import PaletteEntry


def _draw_smoothed_outlines(
    canvas: np.ndarray,
    label_img: np.ndarray,
    thickness: int,
    importance_map: np.ndarray | None = None,
) -> None:
    """Draw simplified + Chaikin-smoothed per-label contours (see ``contours``),
    so on-screen line art matches the SVG's smooth outlines rather than the raw
    pixel-diff staircase a boundary walk would produce.
    """
    for lbl in np.unique(label_img):
        mask = (label_img == lbl).astype(np.uint8)
        for c in contours.smoothed_contours(mask, importance_map=importance_map):
            pts = np.round(c).astype(np.int32).reshape(-1, 1, 2)
            cv2.polylines(
                canvas, [pts], isClosed=True, color=(0, 0, 0),
                thickness=thickness, lineType=cv2.LINE_AA,
            )


def line_art(
    label_img: np.ndarray,
    palette: list[PaletteEntry],
    *,
    thickness: int = 1,
    min_label_radius: float = 6.0,
    draw_numbers: bool = True,
    importance_map: np.ndarray | None = None,
) -> np.ndarray:
    """Compose an RGB uint8 canvas: white background, smoothed black outlines + numbers."""
    h, w = label_img.shape
    canvas = np.full((h, w, 3), 255, dtype=np.uint8)

    _draw_smoothed_outlines(canvas, label_img, thickness, importance_map=importance_map)

    if draw_numbers:
        for entry in palette:
            _label_regions(canvas, label_img, entry.index, min_label_radius)

    return canvas


def _label_regions(
    canvas: np.ndarray,
    label_img: np.ndarray,
    index: int,
    min_label_radius: float,
) -> None:
    """Draw `index` inside every sufficiently large component of that label.

    Placement uses the pole of inaccessibility (see ``numbering``) so the digit
    lands at the region's most interior point even for concave shapes. A
    component whose inscribed radius is below ``min_label_radius`` is left
    unnumbered — the color still appears in the legend.
    """
    mask = (label_img == index - 1).astype(np.uint8)
    n, comp, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=4)

    for c in range(1, n):
        x, y, bw, bh, area = stats[c]
        if area < 16:
            continue

        crop = (comp[y:y + bh, x:x + bw] == c).astype(np.uint8)
        rx, ry, radius = numbering.interior_point(crop)
        if radius < min_label_radius:
            continue

        anchor = (int(x + rx), int(y + ry))
        _put_centered_number(canvas, str(index), anchor, radius)


def painted_preview(label_img: np.ndarray, palette: list[PaletteEntry]) -> np.ndarray:
    """Render the label map filled with palette colors — a preview of the
    finished painting. Cheap (a lookup table) and a big UX cue for the user.
    """
    h, w = label_img.shape
    lut = np.full((len(palette) + 1, 3), 255, dtype=np.uint8)
    for entry in palette:
        rgb = tuple(int(entry.hex[j:j + 2], 16) for j in (1, 3, 5))
        lut[entry.index - 1] = rgb
    idx = np.clip(label_img, 0, len(palette) - 1) if palette else label_img
    return lut[idx]


def _put_centered_number(
    canvas: np.ndarray,
    text: str,
    anchor: tuple[int, int],
    radius: float,
) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    # Scale the glyph so it comfortably fits inside the inscribed circle.
    font_scale = max(0.3, min(radius / 18.0, 2.5))
    thickness = max(1, int(round(font_scale * 1.6)))

    (tw, th), _ = cv2.getTextSize(text, font, font_scale, thickness)
    org = (int(anchor[0] - tw / 2), int(anchor[1] + th / 2))
    cv2.putText(canvas, text, org, font, font_scale, (0, 0, 0), thickness, cv2.LINE_AA)
