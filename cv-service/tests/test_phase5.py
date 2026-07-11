"""Phase 5: edge-aware quantization, pole-of-inaccessibility numbering, SVG."""

import numpy as np
from skimage.color import rgb2lab

from app import numbering, render, superpixels, vectorize
from app.cache import PaletteEntry


def test_superpixel_quantize_separates_clear_colors(solid_blocks_rgb):
    """On a 4-block image the edge-aware quantizer must recover ~4 colors and a
    label map whose boundaries line up with the block seams, not noise.
    """
    lab = rgb2lab(solid_blocks_rgb.astype(np.float64) / 255.0)
    label_map, centroids = superpixels.quantize(lab, n_segments=400, k=4)

    assert label_map.shape == solid_blocks_rgb.shape[:2]
    assert centroids.shape[1] == 3
    # Four blocks → four dominant labels covering essentially the whole image.
    _, counts = np.unique(label_map, return_counts=True)
    big = counts[counts > label_map.size * 0.1]
    assert 3 <= len(big) <= 5


def test_accent_seeding_keeps_near_white_population_distinct(monkeypatch):
    """A large near-white population (daisies against a warm background) must
    keep its own palette slot instead of being diluted into the surrounding
    warm cluster (docs/issues/landscape-quality, Problem 2). Without seeding
    (disabled here as the control), a small k lets plain area-weighted
    k-means fold the near-white minority into the dominant warm mass.
    """
    from app import config, superpixels

    h, w = 120, 120
    rgb = np.full((h, w, 3), (230, 150, 60), dtype=np.uint8)  # warm background
    rgb[90:, :] = (250, 248, 245)  # near-white strip along the bottom (~25% area)
    lab = rgb2lab(rgb.astype(np.float64) / 255.0)

    sp = superpixels.oversegment(lab, n_segments=200)

    monkeypatch.setattr(config, "PALETTE_ACCENT_SEEDING", True)
    _, centroids_seeded = superpixels.palette_from_superpixels(lab, sp, k=3)

    monkeypatch.setattr(config, "PALETTE_ACCENT_SEEDING", False)
    _, centroids_plain = superpixels.palette_from_superpixels(lab, sp, k=3)

    near_white_lab = rgb2lab(np.array([[[250, 248, 245]]], dtype=np.float64) / 255.0).reshape(3)

    def closest_l(centroids):
        return float(centroids[np.argmin(np.abs(centroids[:, 0] - near_white_lab[0])), 0])

    # Seeding must land a centroid closer to the true near-white lightness
    # than the plain (unseeded) fit does.
    assert abs(closest_l(centroids_seeded) - near_white_lab[0]) <= abs(
        closest_l(centroids_plain) - near_white_lab[0]
    )
    assert closest_l(centroids_seeded) >= config.PALETTE_ACCENT_L_MIN


def test_accent_seeding_disabled_matches_plain_kmeans_call(monkeypatch):
    """PALETTE_ACCENT_SEEDING=False must reproduce the exact prior
    KMeans(random_state=42, n_init=3) call, byte-for-byte."""
    from sklearn.cluster import KMeans

    from app import config, superpixels

    monkeypatch.setattr(config, "PALETTE_ACCENT_SEEDING", False)
    rgb = solid_blocks_rgb_for_test()
    lab = rgb2lab(rgb.astype(np.float64) / 255.0)
    sp = superpixels.oversegment(lab, n_segments=200)

    _, centroids = superpixels.palette_from_superpixels(lab, sp, k=4)

    means, area = superpixels.superpixel_means(lab, sp)
    expected = KMeans(n_clusters=4, random_state=42, n_init=3)
    expected.fit(means, sample_weight=area)

    assert np.allclose(centroids, expected.cluster_centers_)


def solid_blocks_rgb_for_test() -> np.ndarray:
    img = np.zeros((200, 200, 3), dtype=np.uint8)
    img[:100, :100] = (230, 40, 40)
    img[:100, 100:] = (40, 200, 60)
    img[100:, :100] = (40, 80, 230)
    img[100:, 100:] = (230, 210, 40)
    return img


def test_interior_point_lands_inside_a_C_shape():
    """The pole of inaccessibility must be inside the mask, never in the
    concavity of a C — the failure mode of a naive centroid.
    """
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[20:80, 20:80] = 1       # solid square
    mask[35:65, 40:100] = 0      # bite a C-mouth out of the right side

    x, y, radius = numbering.interior_point(mask)

    assert radius > 0
    assert mask[int(round(y)), int(round(x))] == 1  # point is on the region


def test_painted_preview_fills_palette_colors():
    label_img = np.zeros((10, 10), dtype=np.int32)
    label_img[:, 5:] = 1
    palette = [
        PaletteEntry(index=1, hex="#FF0000", lab=(53.0, 80.0, 67.0), name_ru="красный"),
        PaletteEntry(index=2, hex="#00FF00", lab=(88.0, -86.0, 83.0), name_ru="зелёный"),
    ]
    preview = render.painted_preview(label_img, palette)

    assert preview.shape == (10, 10, 3)
    assert tuple(preview[0, 0]) == (255, 0, 0)   # left half red
    assert tuple(preview[0, 9]) == (0, 255, 0)   # right half green


def test_to_svg_is_wellformed_and_covers_present_colors():
    label_img = np.zeros((60, 60), dtype=np.int32)
    label_img[:, 30:] = 1
    palette = [
        PaletteEntry(index=1, hex="#123456", lab=(20.0, 5.0, -20.0), name_ru="синий"),
        PaletteEntry(index=2, hex="#abcdef", lab=(80.0, 0.0, -10.0), name_ru="голубой"),
    ]
    svg = vectorize.to_svg(label_img, palette)

    assert svg.startswith("<?xml") or svg.lstrip().startswith("<svg")
    assert "<path" in svg
    assert "viewBox" in svg or "viewbox" in svg.lower()
    # Two colors present → at least two region paths.
    assert svg.count("<path") >= 2
    # Per-color highlight hooks: class + the region's own colour as a CSS var.
    assert 'rg-1' in svg and 'rg-2' in svg
    assert '--rc:#123456' in svg
