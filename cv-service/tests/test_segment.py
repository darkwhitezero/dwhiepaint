import numpy as np
from skimage.color import deltaE_ciede2000

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


def test_merge_prefers_weak_gradient_border_over_sharp_one():
    """When two neighbors tie on BOTH border length and color distance, the
    edge-aware term must still break the tie: the small region should merge
    into the neighbor whose shared border sits on a weak image gradient, not
    a sharp real edge.
    """
    region_id = np.array([[1, 0, 2]] * 5, dtype=np.int64)
    region_cluster = np.array([0, 1, 2], dtype=np.int32)
    areas = np.array([5.0, 1000.0, 1000.0])
    min_area = 10

    # Symmetric a*/b* offsets from region 0 -> CIEDE2000 to region 1 and region
    # 2 is numerically identical (verified: both 12.8...), so color is a tie.
    cluster_lab = np.array(
        [[50.0, 0.0, 0.0], [50.0, 10.0, 10.0], [50.0, -10.0, -10.0]], dtype=np.float64,
    )

    # Border(region1, region0) [columns 0-1] sits on a weak gradient; border
    # (region0, region2) [columns 1-2] sits on a strong one.
    gradient_mag = np.array([[0.05, 0.05, 1.75]] * 5, dtype=np.float32)

    cleaned = segment.merge_small_regions(
        region_id, region_cluster, areas, min_area,
        cluster_lab=cluster_lab, gradient_mag=gradient_mag,
    )

    # The tiny region's pixels (middle column) must take the weak-border
    # neighbor's cluster id (1), not the sharp-border one (2).
    assert np.all(cleaned[:, 1] == 1)


def test_merge_gradient_term_is_noop_without_gradient_mag():
    """Regression guard: the existing color-tiebreak test must still pass
    unchanged when gradient_mag isn't passed (the CIEDE2000 swap alone must
    not flip its outcome).
    """
    region_id = np.array([[1, 0, 2]] * 5, dtype=np.int64)
    region_cluster = np.array([0, 1, 2], dtype=np.int32)
    areas = np.array([5.0, 1000.0, 1000.0])
    min_area = 10
    cluster_lab = np.array(
        [[50.0, 0.0, 0.0], [52.0, 1.0, 1.0], [90.0, 40.0, 40.0]], dtype=np.float64,
    )

    cleaned = segment.merge_small_regions(
        region_id, region_cluster, areas, min_area, cluster_lab=cluster_lab,
    )
    assert np.all(cleaned[:, 1] == 1)


def test_merge_elongation_forces_thin_sliver_but_spares_compact_region(monkeypatch):
    """A thin, wiggly-shaped micro-region (a flower-stem fragment) must merge
    away even when its raw area already clears min_area, because its shape
    alone makes it unpaintable (docs/issues/landscape-quality, Problem 1); an
    equal-area COMPACT region under the same threshold must be left alone.
    """
    from app import config
    monkeypatch.setattr(config, "MERGE_ELONGATION_MIN_AREA_MULT", 2.5)
    monkeypatch.setattr(config, "MERGE_ELONGATION_SHAPE_THRESHOLD", 4.0)

    h, w = 20, 40
    labels = np.zeros((h, w), dtype=np.int32)  # cluster 0 = background
    labels[5, 2:18] = 1     # thin 16px-long, 1px-wide line -> cluster 1
    labels[10:14, 2:6] = 2  # compact 4x4 block (also 16px) -> cluster 2

    region_id, region_cluster, areas = segment.connected_regions(labels, 3)
    cleaned = segment.merge_small_regions(region_id, region_cluster, areas, min_area=10)

    assert not np.any(cleaned == 1)  # thin sliver merged away despite area >= min_area
    assert np.any(cleaned == 2)      # compact region of the same area survives


def test_merge_elongation_disabled_leaves_thin_sliver_alone(monkeypatch):
    """MULT<=1.0 must reproduce pre-Phase-17 behavior: raw area alone decides,
    so the same thin sliver (area already >= min_area) is left untouched.
    """
    from app import config
    monkeypatch.setattr(config, "MERGE_ELONGATION_MIN_AREA_MULT", 1.0)

    h, w = 20, 40
    labels = np.zeros((h, w), dtype=np.int32)
    labels[5, 2:18] = 1
    labels[10:14, 2:6] = 2

    region_id, region_cluster, areas = segment.connected_regions(labels, 3)
    cleaned = segment.merge_small_regions(region_id, region_cluster, areas, min_area=10)

    assert np.any(cleaned == 1)  # unchanged behavior: raw area already clears min_area


def test_palette_separation_pushes_near_duplicates_apart():
    """Near-identical colors should still be nudged toward distinctness so two
    different numbers don't read as the same swatch on the legend.
    """
    labs = [np.array([50.0, 0.0, 0.0]), np.array([50.4, 0.0, 0.0])]

    out = segment._separate_similar_colors([lab.copy() for lab in labs])

    before = float(deltaE_ciede2000(labs[0].reshape(1, 3), labs[1].reshape(1, 3))[0])
    after = float(deltaE_ciede2000(out[0].reshape(1, 3), out[1].reshape(1, 3))[0])
    assert after > before


def test_palette_separation_never_misrepresents_a_color():
    """The separated color is what the painted preview and the printed legend
    are actually filled with, so it must never drift further from the color
    measured in the photo than PALETTE_MAX_SHIFT_DELTA_E — separation gives up
    and tolerates a collision rather than paint a visibly wrong color.

    Regression guard: a long run of near-duplicates used to ratchet, because
    each entry only had to clear the PREVIOUS (already-pushed) one. Measured
    on a real landscape that drove the brightest entry +12 L off its true
    color.
    """
    from app import config

    labs = [np.array([40.0 + 0.4 * i, 0.0, 0.0]) for i in range(12)]

    out = segment._separate_similar_colors([lab.copy() for lab in labs])

    assert len(out) == len(labs)
    for original, shown in zip(labs, out):
        drift = float(deltaE_ciede2000(original.reshape(1, 3), shown.reshape(1, 3))[0])
        assert drift <= config.PALETTE_MAX_SHIFT_DELTA_E + 1e-6


def test_palette_is_ordered_by_true_lightness():
    """The legend is documented (and drawn) dark->light. Ordering by RGB
    average only approximates that and is not monotonic in L — on a real photo
    it inverted in 6 places, which also made the separation sweep cascade.
    """
    h, w = 10, 40
    cleaned = np.zeros((h, w), dtype=np.int32)
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    # A saturated blue and a yellow chosen so RGB-average and L disagree:
    # yellow is far lighter than blue despite a similar channel average.
    swatches = [(40, 40, 40), (30, 30, 200), (220, 220, 40), (245, 245, 245)]
    for i, color in enumerate(swatches):
        cleaned[:, i * 10 : (i + 1) * 10] = i
        rgb[:, i * 10 : (i + 1) * 10] = color

    _, palette = segment._build_palette(cleaned, rgb)

    lightness = [p.lab[0] for p in palette]
    assert lightness == sorted(lightness)
