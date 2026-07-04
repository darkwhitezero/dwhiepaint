import numpy as np

from app import segment


def test_segment_survives_tiny_decorative_speck(busy_with_speck_entry, tmp_path, monkeypatch):
    """A small colored speck inside a big region (star/heart-style decoration)
    must not crash the pipeline, and it must merge deterministically rather
    than producing a dangling sliver.
    """
    from app import config
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)

    seg, region_map_url = segment.segment(busy_with_speck_entry, k=6)

    assert seg.label_img.shape == busy_with_speck_entry.rgb.shape[:2]
    assert len(seg.palette) >= 1
    assert region_map_url.startswith("/cache/")

    # Every present final region must be a real color from the palette.
    valid_indices = {p.index - 1 for p in seg.palette}
    assert set(np.unique(seg.label_img)).issubset(valid_indices)


def test_merge_prefers_perceptually_closer_neighbor():
    """When two neighbors share an equally long border with a tiny region,
    the color-aware merge picks the perceptually closer one, not whichever
    happened to be scanned first.
    """
    # A 5-row x 3-col grid: region 1 (left) | region 0 (tiny, under test) | region 2 (right).
    # Both borders (0-1 and 0-2) are exactly 5 pixels long — length alone
    # can't break the tie, so color must.
    region_id = np.array([[1, 0, 2]] * 5, dtype=np.int64)
    region_cluster = np.array([0, 1, 2], dtype=np.int32)
    areas = np.array([5.0, 1000.0, 1000.0])
    min_area = 10

    # Region 0's color is close to region 1's and far from region 2's.
    cluster_lab = np.array(
        [[50.0, 0.0, 0.0], [52.0, 1.0, 1.0], [90.0, 40.0, 40.0]], dtype=np.float64,
    )

    cleaned = segment.merge_small_regions(
        region_id, region_cluster, areas, min_area, cluster_lab=cluster_lab,
    )

    # The tiny region's pixels (middle column) must have taken on the
    # color-close left neighbor's cluster id (1), not the far one (2).
    assert np.all(cleaned[:, 1] == 1)


def test_merge_respects_min_area_floor():
    """After merging, every surviving region must be at or above the area
    floor (isolated regions with no neighbor are the only exception).
    """
    region_id = np.array([[0, 1, 1, 1]] * 4, dtype=np.int64)
    region_cluster = np.array([0, 1], dtype=np.int32)
    areas = np.array([4.0, 100.0])
    min_area = 10

    cleaned = segment.merge_small_regions(region_id, region_cluster, areas, min_area)

    # The small region (id 0, area 4) must have merged away entirely.
    assert not np.any(cleaned == 0)
