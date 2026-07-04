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
