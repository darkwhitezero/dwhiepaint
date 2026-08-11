"""Paintability metrics: how much of a result a person can actually fill in.

Region area is a poor proxy for "can this be painted". What decides it is
whether a NUMBER fits inside the region — an unnumbered region is unpaintable
because nothing tells the painter which colour it takes. ``vectorize.to_svg``
already answers that per region and then discards the answer; this module
counts it, using the same rule so the metric and the rendered sheet can never
disagree.
"""

from __future__ import annotations

import cv2
import numpy as np

from . import config, numbering


def paintability(
    label_img: np.ndarray,
    *,
    min_label_radius: float | None = None,
    min_component_area: int = 16,
) -> dict:
    """Count the regions the numbering step will leave unlabelled.

    Mirrors ``vectorize.to_svg``: 4-connected components per colour index,
    components under ``min_component_area`` ignored as quantization specks,
    and a component labelled only when its pole of inaccessibility clears
    ``min_label_radius`` — which defaults to the same config value the renderer
    uses, so the metric cannot drift away from the sheet it describes.
    Iterating ``np.unique`` instead of the palette is equivalent — label_img
    holds exactly the 0-based palette indices — and keeps the metric usable
    without building a palette first.
    """
    min_radius = config.LABEL_MIN_RADIUS_PX if min_label_radius is None else min_label_radius
    total = unlabelled = unlabelled_px = 0

    for idx in np.unique(label_img):
        mask = (label_img == idx).astype(np.uint8)
        n, comp, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=4)
        for c in range(1, n):
            x, y, bw, bh, area = stats[c]
            if area < min_component_area:
                continue
            total += 1
            crop = (comp[y:y + bh, x:x + bw] == c).astype(np.uint8)
            _, _, radius = numbering.interior_point(crop)
            if radius < min_radius:
                unlabelled += 1
                unlabelled_px += int(area)

    px = int(label_img.size)
    return {
        "regions": total,
        "unlabelled": unlabelled,
        "unlabelled_frac": unlabelled / total if total else 0.0,
        "unlabelled_area_frac": unlabelled_px / px if px else 0.0,
    }
