import io

import numpy as np
from PIL import Image

from app import analyze, config, render
from app import export as export_mod
from app import segment as segment_mod


def _png_bytes(rgb) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="PNG")
    return buf.getvalue()


def test_full_pipeline_pdf_and_png(solid_blocks_rgb, tmp_path, monkeypatch):
    """analyze -> segment -> export(pdf & png) end-to-end, at the configured
    DPI/page size — the same path a real upload takes.
    """
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)

    result = analyze.analyze(_png_bytes(solid_blocks_rgb))
    image_id = result["image_id"]
    entry = analyze.cache.get(image_id)
    assert entry is not None

    segment_mod.segment(entry, k=result["predicted_k"])

    pdf_bytes = export_mod.compose_export(entry, "A4", True)
    assert pdf_bytes[:5] == b"%PDF-"

    png_bytes = export_mod.compose_png(entry, "A4")
    img = Image.open(io.BytesIO(png_bytes))
    assert img.size == config.PAGE_SIZES_PX["A4"]


def test_painted_png_is_unbranded_and_working_resolution(solid_blocks_rgb, tmp_path, monkeypatch):
    """The 'painted' export (for sharing the result, not printing) must be
    just the colored artwork — no dwhiepaint title, no reference thumbnails,
    no page composition — at the working resolution, not the print page size.
    """
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)

    result = analyze.analyze(_png_bytes(solid_blocks_rgb))
    entry = analyze.cache.get(result["image_id"])
    assert entry is not None
    segment_mod.segment(entry, k=result["predicted_k"])

    seg = entry.segmentation
    png_bytes = export_mod.compose_painted_png(entry)
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")

    # Working resolution (label_img shape), NOT a print page size.
    assert img.size == (seg.label_img.shape[1], seg.label_img.shape[0])
    assert img.size != config.PAGE_SIZES_PX["A4"]

    # Pixel-identical to the raw painted preview — proves no title/thumbnail/
    # page composition was baked in on top.
    expected = render.painted_preview(seg.label_img, seg.palette)
    assert np.array_equal(np.asarray(img), expected)
