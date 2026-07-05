"""Phase 7 (subject-aware detail) unit coverage that doesn't need rembg:
the per-region min-area merge and the importance→min-area mapping. Synthetic
images stay below SUBJECT_MIN_SIDE so matting is skipped and tests are fast.
"""

from __future__ import annotations

import numpy as np

from app import config, segment


def _three_stripes(mid_lo: int = 40, mid_hi: int = 50):
    """Left/middle/right stripes as clusters 0/1/2; middle is the small one."""
    labels = np.zeros((30, 100), np.int32)
    labels[:, :mid_lo] = 0
    labels[:, mid_lo:mid_hi] = 1
    labels[:, mid_hi:] = 2
    return segment.connected_regions(labels, 3)


def test_per_region_min_area_keeps_important_merges_unimportant():
    rid, rc, areas = _three_stripes()

    # Middle region (id 1, area 300) with a low threshold survives.
    kept = segment.merge_small_regions(rid, rc, areas, np.array([500.0, 100.0, 500.0]))
    assert len(np.unique(kept)) == 3

    # Same geometry, but a high threshold everywhere absorbs the middle.
    merged = segment.merge_small_regions(rid, rc, areas, np.array([500.0, 500.0, 500.0]))
    assert len(np.unique(merged)) == 2


def test_scalar_min_area_backcompat_still_merges():
    rid, rc, areas = _three_stripes()
    out = segment.merge_small_regions(rid, rc, areas, 500)  # scalar path
    assert len(np.unique(out)) == 2


def test_region_min_area_is_inverse_to_importance():
    labels = np.zeros((10, 30), np.int32)
    labels[:, :10] = 0
    labels[:, 10:20] = 1
    labels[:, 20:] = 2
    rid, _, areas = segment.connected_regions(labels, 3)

    imp = np.full((10, 30), 0.1, np.float32)
    imp[:, 10:20] = 1.5  # high importance on the middle region

    ma = segment._region_min_area(rid, areas, imp, base_min_area=1000)
    assert ma[1] < ma[0]  # important region gets a smaller minimum area
    assert ma.min() >= config.MIN_AREA_HARD_FLOOR


def test_importance_map_soft_fallback_on_small_image():
    from app import importance

    rgb = np.random.default_rng(0).integers(0, 255, (64, 64, 3), dtype=np.uint8)
    imp, meta = importance.importance_map(rgb)
    assert imp.shape == (64, 64)
    assert meta["subject"] is False  # below SUBJECT_MIN_SIDE → matting skipped
    assert float(imp.min()) >= 0.0
