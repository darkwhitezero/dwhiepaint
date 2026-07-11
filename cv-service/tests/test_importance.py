"""Phase 17 (landscape quality, Issue #2): global edge-damping when no subject
is found. Synthetic images stay below SUBJECT_MIN_SIDE so matting is skipped
deterministically (no rembg model needed, no network) — same pattern as
test_phase7.py's small-image fixtures.
"""

from __future__ import annotations

import numpy as np

from app import config, importance


def _busy_checkerboard(h: int = 200, w: int = 200) -> np.ndarray:
    """High-contrast texture with no coherent subject — a stand-in for a
    field of flowers/foliage: uniformly strong edges everywhere, exactly the
    shape that made the old importance map treat the whole frame as
    "important" (docs/issues/landscape-quality, Problem 1).
    """
    xx, yy = np.meshgrid(np.arange(w), np.arange(h))
    checker = (((xx // 4) + (yy // 4)) % 2).astype(np.uint8) * 255
    return np.stack([checker, checker, checker], axis=-1)


def test_no_subject_edge_damp_lowers_busy_texture_importance(monkeypatch):
    rgb = _busy_checkerboard()

    imp_damped, meta = importance.importance_map(rgb)
    assert meta["subject"] is False  # below SUBJECT_MIN_SIDE -> matting skipped

    monkeypatch.setattr(config, "IMPORTANCE_NO_SUBJECT_EDGE_DAMP", 0.0)
    imp_undamped, _ = importance.importance_map(rgb)

    assert float(imp_damped.mean()) < float(imp_undamped.mean())
    # The floor must never be violated regardless of how hard we damp.
    assert float(imp_damped.min()) >= config.IMPORTANCE_FLOOR - 1e-6


def test_no_subject_edge_damp_matches_plain_formula_when_disabled(monkeypatch):
    """DAMP=0 must reproduce the pre-Phase-17 no-subject formula exactly:
    FLOOR + W_EDGE * edges, with no further correction applied.
    """
    rgb = _busy_checkerboard()
    monkeypatch.setattr(config, "IMPORTANCE_NO_SUBJECT_EDGE_DAMP", 0.0)

    imp, meta = importance.importance_map(rgb)
    assert meta["subject"] is False

    edges = importance._edge_saliency(rgb)
    expected = config.IMPORTANCE_FLOOR + config.IMPORTANCE_W_EDGE * edges
    assert np.allclose(imp, expected, atol=1e-5)
