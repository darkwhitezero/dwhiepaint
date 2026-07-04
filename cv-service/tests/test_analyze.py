from skimage.color import rgb2lab

from app import analyze


def test_auto_k_stays_modest_on_a_simple_four_block_image(solid_blocks_rgb):
    """A trivially simple 4-color image shouldn't make the heavier auto-k
    search reach for a large, over-fragmented k — regression guard against
    the search over-fitting to noise instead of real structure.
    """
    lab = rgb2lab(solid_blocks_rgb.astype("float64") / 255.0)

    k = analyze._auto_k(lab)

    assert analyze.config.MIN_K <= k <= analyze.config.MAX_K
    assert k <= 12  # comfortably below the candidate grid's upper end (30)


def test_score_candidate_returns_none_for_degenerate_k(solid_blocks_rgb):
    """Requesting more clusters than there are pixels must not explode."""
    lab = rgb2lab(solid_blocks_rgb.astype("float64") / 255.0)
    working = analyze._downsample_lab(lab, analyze.config.AUTO_K_WORKING_MAX_SIDE)

    # k == 1 collapses to a single cluster — silhouette needs >= 2 labels.
    assert analyze._score_candidate(working, 1) is None
