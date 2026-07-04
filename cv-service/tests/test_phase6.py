"""Phase 6 (async jobs) unit coverage that doesn't need a live Redis/worker:
the progress callback wiring, on-disk image reconstruction, and the pure
status-projection helpers.
"""

from __future__ import annotations

import numpy as np
from skimage.color import rgb2lab

from app import cache, jobs, segment as segment_mod, storage
from app.cache import ImageEntry


def _three_block_entry(image_id: str = "phase6") -> ImageEntry:
    rgb = np.zeros((120, 120, 3), np.uint8)
    rgb[:40] = (210, 40, 40)
    rgb[40:80] = (40, 200, 60)
    rgb[80:] = (40, 60, 210)
    lab = rgb2lab(rgb.astype(np.float64) / 255.0)
    return ImageEntry(image_id=image_id, rgb=rgb, lab=lab)


def test_segment_reports_monotonic_progress_ending_done():
    events: list[tuple[str, float]] = []
    segment_mod.segment(_three_block_entry(), k=3, progress=lambda s, f: events.append((s, f)))

    assert events, "expected progress callbacks"
    fractions = [f for _, f in events]
    assert fractions == sorted(fractions), "progress must not go backwards"
    assert events[-1] == ("done", 1.0)
    names = {s for s, _ in events}
    assert {"superpixels", "merge", "vectorize"} <= names


def test_load_entry_roundtrips_pixels_from_disk():
    rgb = np.zeros((24, 24, 3), np.uint8)
    rgb[:, :12] = (10, 150, 240)  # asymmetric so channel order is checked
    image_id = "roundtrip-p6"
    storage.save_rgb_png(image_id, "preview.png", rgb)

    entry = cache.load_entry(image_id)
    assert entry is not None
    assert np.array_equal(entry.rgb, rgb)  # PNG is lossless; RGB order preserved
    assert entry.lab.shape == rgb.shape


def test_load_entry_missing_returns_none():
    assert cache.load_entry("definitely-not-a-real-image-id") is None


def test_status_view_hides_result_blob():
    view = jobs.status_view(
        {"status": "processing", "stage": "merge", "progress": "0.5", "result": "{...}"}
    )
    assert view == {"status": "processing", "stage": "merge", "progress": 0.5}


def test_status_view_surfaces_error():
    view = jobs.status_view({"status": "failed", "stage": "failed", "progress": "0", "error": "boom"})
    assert view["status"] == "failed"
    assert view["error"] == "boom"


def test_decode_normalizes_bytes_and_str():
    assert jobs._decode({b"a": b"1", "b": "2"}) == {"a": "1", "b": "2"}
