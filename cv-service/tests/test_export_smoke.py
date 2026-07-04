import io

from PIL import Image

from app import analyze, config
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
