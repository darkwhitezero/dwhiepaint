"""Rendering helpers: region outlines and region numbers on a white canvas."""

from __future__ import annotations

import cv2
import numpy as np

from .cache import PaletteEntry


def outline_mask(label_img: np.ndarray) -> np.ndarray:
    """Boolean HxW mask that is True on borders between different labels."""
    h_diff = np.zeros(label_img.shape, dtype=bool)
    v_diff = np.zeros(label_img.shape, dtype=bool)
    h_diff[:, :-1] = label_img[:, :-1] != label_img[:, 1:]
    v_diff[:-1, :] = label_img[:-1, :] != label_img[1:, :]
    return h_diff | v_diff


def line_art(
    label_img: np.ndarray,
    palette: list[PaletteEntry],
    *,
    thickness: int = 1,
    min_label_radius: float = 6.0,
    draw_numbers: bool = True,
) -> np.ndarray:
    """Compose an RGB uint8 canvas: white background, black outlines + numbers."""
    h, w = label_img.shape
    canvas = np.full((h, w, 3), 255, dtype=np.uint8)

    lines = outline_mask(label_img)
    if thickness > 1:
        kernel = np.ones((thickness, thickness), np.uint8)
        lines = cv2.dilate(lines.astype(np.uint8), kernel).astype(bool)
    canvas[lines] = (0, 0, 0)

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
    """Draw `index` inside every sufficiently large component of that label."""
    mask = (label_img == index - 1).astype(np.uint8)
    n, comp, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=4)

    for c in range(1, n):
        x, y, bw, bh, area = stats[c]
        if area < 16:
            continue

        crop = (comp[y:y + bh, x:x + bw] == c).astype(np.uint8)
        dt = cv2.distanceTransform(crop, cv2.DIST_L2, 3)
        radius = float(dt.max())
        if radius < min_label_radius:
            continue

        ry, rx = np.unravel_index(int(np.argmax(dt)), dt.shape)
        anchor = (x + rx, y + ry)

        _put_centered_number(canvas, str(index), anchor, radius)


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
