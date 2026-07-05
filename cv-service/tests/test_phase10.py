"""Phase 10 (physical layer): paint matching + tiled multi-page export."""

from __future__ import annotations

import numpy as np
from skimage.color import rgb2lab

from app import export, paints
from app.cache import ImageEntry, PaletteEntry, Segmentation


def _entry() -> ImageEntry:
    rgb = np.zeros((60, 60, 3), np.uint8)
    rgb[:, :30] = (200, 30, 30)
    rgb[:, 30:] = (30, 30, 200)
    label = np.zeros((60, 60), np.int32)
    label[:, 30:] = 1
    palette = [
        PaletteEntry(index=1, hex="#C81E1E", lab=(40.0, 60.0, 40.0), name_ru="красный"),
        PaletteEntry(index=2, hex="#1E1EC8", lab=(30.0, 50.0, -60.0), name_ru="синий"),
    ]
    e = ImageEntry(image_id="x", rgb=rgb, lab=rgb.astype(np.float64))
    e.segmentation = Segmentation(k=2, label_img=label, palette=palette)
    return e


def test_nearest_paint_for_white_is_titanium():
    white_lab = tuple(float(v) for v in rgb2lab(np.ones((1, 1, 3))).reshape(3))
    paint, de = paints.nearest(white_lab)
    assert "Белила" in paint["name_ru"]
    assert de < 6.0


def test_describe_returns_paint_and_maybe_mix():
    d = paints.describe((55.0, -35.0, -12.0))
    assert d["paint_name"] and d["paint_hex"]
    assert "delta_e" in d
    if "mix" in d:
        assert len(d["mix"]) == 2


def test_compose_tiled_is_multipage_pdf():
    pdf = export.compose_tiled(_entry(), "A4", 2, include_legend=False)
    assert pdf[:4] == b"%PDF"
    # 2×2 → 1 assembly map + 4 tiles = 5 pages (one MediaBox each).
    assert pdf.count(b"/MediaBox") >= 5
