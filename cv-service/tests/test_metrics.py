import numpy as np

from app import metrics


def test_paintability_counts_regions_that_cannot_hold_a_number():
    """A region is unpaintable when no number fits inside it: nothing tells the
    painter which colour it takes. Region area alone doesn't capture that — a
    long thin sliver can clear an area threshold and still end up unlabelled.
    """
    label_img = np.zeros((120, 200), dtype=np.int32)
    label_img[20:100, 20:100] = 1     # 80x80 square: a number fits easily
    label_img[50:53, 120:190] = 2     # 3px-tall sliver: 210px of area, no room

    stats = metrics.paintability(label_img)

    assert stats["regions"] == 3      # background + square + sliver
    assert stats["unlabelled"] == 1   # only the sliver
    assert 0.0 < stats["unlabelled_frac"] < 1.0
    assert stats["unlabelled_area_frac"] > 0.0


def test_paintability_is_zero_on_a_clean_two_region_image():
    label_img = np.zeros((120, 200), dtype=np.int32)
    label_img[:, 100:] = 1

    stats = metrics.paintability(label_img)

    assert stats["regions"] == 2
    assert stats["unlabelled"] == 0
    assert stats["unlabelled_frac"] == 0.0
