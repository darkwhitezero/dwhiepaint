"""Phase 11 (robustness): the pipeline must survive degenerate inputs without
crashing and always yield a valid palette + SVG. Subject-aware matting is off
here so the regression stays fast and hermetic (no rembg model needed)."""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

from app import analyze, config, segment, vectorize
from app.cache import cache

config.SUBJECT_AWARE = False


def _png(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


CASES = {
    "monochrome": np.full((300, 400, 3), (120, 60, 180), np.uint8),
    "tiny": np.random.default_rng(1).integers(0, 255, (24, 24, 3)).astype(np.uint8),
    "extreme_aspect": np.random.default_rng(2).integers(0, 255, (40, 3000, 3)).astype(np.uint8),
    "pure_noise": np.random.default_rng(3).integers(0, 255, (400, 400, 3)).astype(np.uint8),
    "two_color": np.concatenate(
        [np.full((240, 240, 3), (230, 20, 20), np.uint8),
         np.full((240, 240, 3), (20, 20, 230), np.uint8)], axis=1
    ),
}


@pytest.mark.parametrize("name", list(CASES))
def test_pipeline_survives_degenerate_inputs(name):
    result = analyze.analyze(_png(CASES[name]))
    entry = cache.get(result["image_id"])
    assert entry is not None
    assert entry.width >= 1 and entry.height >= 1

    seg, url = segment.segment(entry, result["predicted_k"])
    assert 1 <= len(seg.palette) <= config.MAX_K
    assert url.endswith("regions.png")

    svg = vectorize.to_svg(seg.label_img, seg.palette)
    assert svg.lstrip().startswith("<")


def test_analyze_rejects_broken_bytes():
    with pytest.raises(Exception):
        analyze.analyze(b"this is definitely not an image")
