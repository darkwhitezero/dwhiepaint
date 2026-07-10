"""Regression coverage for the worker/API cross-process segmentation gap:
the async job path segments in the WORKER container, a separate process from
the cv-service API container (they share only CACHE_DIR and Redis, never
in-memory state). Before this fix, /export always saw entry.segmentation as
None on the API container's copy and 409'd — even though segmentation had
genuinely completed — because nothing persisted the label map/palette
anywhere a different process could read them back from.
"""
import numpy as np

from app import segment
from app.cache import ImageEntry, ensure_segmentation, save_segmentation


def test_ensure_segmentation_reconstructs_across_processes(
    busy_with_speck_entry, tmp_path, monkeypatch,
):
    from app import config
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)

    # Simulates the worker: runs segment() (which now also persists to disk)
    # on its own ImageEntry object.
    seg, _ = segment.segment(busy_with_speck_entry, k=6)
    assert busy_with_speck_entry.segmentation is not None

    # Simulates the API container: a FRESH ImageEntry for the same image_id,
    # as load_entry() would build from preview.png — segment() never ran on
    # THIS object, so segmentation starts out None.
    fresh_entry = ImageEntry(
        image_id=busy_with_speck_entry.image_id,
        rgb=busy_with_speck_entry.rgb,
        lab=busy_with_speck_entry.lab,
    )
    assert fresh_entry.segmentation is None

    reconstructed = ensure_segmentation(fresh_entry)

    assert reconstructed is not None
    assert fresh_entry.segmentation is reconstructed  # cached onto the entry
    assert reconstructed.k == seg.k
    assert reconstructed.label_img.shape == seg.label_img.shape
    assert np.array_equal(reconstructed.label_img, seg.label_img)
    assert len(reconstructed.palette) == len(seg.palette)
    assert [p.hex for p in reconstructed.palette] == [p.hex for p in seg.palette]
    assert reconstructed.svg_url == seg.svg_url


def test_ensure_segmentation_is_noop_when_already_set(busy_with_speck_entry, tmp_path, monkeypatch):
    """If this process's entry already has a segmentation, ensure_segmentation
    must return it as-is without touching disk.
    """
    from app import config
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)

    seg, _ = segment.segment(busy_with_speck_entry, k=6)
    assert ensure_segmentation(busy_with_speck_entry) is seg


def test_ensure_segmentation_returns_none_for_unsegmented_image(tmp_path, monkeypatch):
    """An image that was never segmented (or whose cache dir was pruned) must
    report None, not raise — the caller (main.py's /export) turns this into a
    409, not a 500.
    """
    from app import config
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)

    entry = ImageEntry(
        image_id="never-segmented",
        rgb=np.zeros((10, 10, 3), dtype=np.uint8),
        lab=np.zeros((10, 10, 3), dtype=np.float64),
    )
    assert ensure_segmentation(entry) is None
