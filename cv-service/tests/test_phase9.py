"""Phase 9 (export formats): SVG export, ZIP bundle, and the PDF with reference."""

from __future__ import annotations

import io
import zipfile

import numpy as np

from app import export
from app.cache import ImageEntry, PaletteEntry, Segmentation


def _entry() -> ImageEntry:
    rgb = np.zeros((40, 40, 3), np.uint8)
    rgb[:, :20] = (200, 30, 30)
    rgb[:, 20:] = (30, 30, 200)
    label = np.zeros((40, 40), np.int32)
    label[:, 20:] = 1
    palette = [
        PaletteEntry(index=1, hex="#C81E1E", lab=(40.0, 60.0, 40.0), name_ru="красный"),
        PaletteEntry(index=2, hex="#1E1EC8", lab=(30.0, 50.0, -60.0), name_ru="синий"),
    ]
    e = ImageEntry(image_id="x", rgb=rgb, lab=rgb.astype(np.float64))
    e.segmentation = Segmentation(k=2, label_img=label, palette=palette)
    return e


def test_export_svg_is_svg_bytes():
    b = export.export_svg(_entry())
    head = b.lstrip()
    assert head.startswith(b"<?xml") or head.startswith(b"<svg")
    assert b"rg-1" in b  # per-colour highlight hooks survive into the export


def test_compose_export_is_pdf():
    assert export.compose_export(_entry())[:4] == b"%PDF"


def test_compose_bundle_zip_has_all_artifacts():
    data = export.compose_bundle(_entry())
    z = zipfile.ZipFile(io.BytesIO(data))
    names = set(z.namelist())
    assert {"raskraska.pdf", "kontur.svg", "predprosmotr.png"} <= names
    assert z.read("raskraska.pdf")[:4] == b"%PDF"
    assert z.read("predprosmotr.png")[:8] == b"\x89PNG\r\n\x1a\n"
