import cv2
import numpy as np
from shapely.geometry import Polygon

from app import config, contours, render


def _thin_hook_mask(h: int = 200, w: int = 200, thickness: int = 4, radius: int = 60) -> np.ndarray:
    """A thin, curving band swept along most of a circle (like a hair strand
    or thin decorative line) — realistic curvature-to-thickness ratio (unlike
    a rapid sine wave, which fragments into disconnected pixel islands whose
    RAW contour is already non-simple before any simplification — verified
    separately; that would stress-test rasterization, not this module). This
    shape's raw findContours output is a single simple polygon, so it isolates
    what CONTOUR_SIMPLIFY_MAX_PX is actually meant to guard: that approxPolyDP
    doesn't self-intersect an otherwise-simple thin region.
    """
    mask = np.zeros((h, w), dtype=np.uint8)
    cx, cy = w // 2, h // 2
    for deg in np.linspace(0, 300, 900):
        rad = np.deg2rad(deg)
        x = int(cx + radius * np.cos(rad))
        y = int(cy + radius * np.sin(rad))
        mask[max(0, y - thickness) : y + thickness, max(0, x - thickness) : x + thickness] = 1
    return mask


def test_smoothed_contours_never_self_intersect():
    """CONTOUR_SIMPLIFY_MAX_PX exists specifically to stop approxPolyDP from
    collapsing a thin region into a self-intersecting polygon (see project
    memory: contour self-intersection). No prior test asserted this directly —
    this one does, at both ends of the importance-driven epsilon range (a
    uniform map at 0 behaves like "no map"; a uniform map at 1 asks for the
    finest/most-detail-preserving epsilon, the highest self-intersection risk).
    """
    mask = _thin_hook_mask()
    shape = mask.shape

    for imp in (
        None,
        np.zeros(shape, dtype=np.float32),
        np.ones(shape, dtype=np.float32),
    ):
        for c in contours.smoothed_contours(mask, importance_map=imp):
            if len(c) < 3:
                continue
            assert Polygon(c).is_simple, "contour self-intersects"


def test_importance_map_preserves_more_detail_than_background():
    """A contour sampled against a high-importance map should keep MORE
    vertices (finer epsilon) than the identical shape with no map (today's
    coarser, uniform CONTOUR_SIMPLIFY_EPS) — importance now reaches contour
    simplification, not just the merge min-area threshold.
    """
    h, w = 200, 400
    label_img = np.zeros((h, w), dtype=np.int32)
    top, bottom, left, right = 50, 150, 50, 350
    for x in range(left, right):
        depth = bottom + (1 if (x // 2) % 2 == 0 else 0)  # 1px staircase noise
        label_img[top:depth, x] = 1
    mask = (label_img == 1).astype(np.uint8)

    background = contours.smoothed_contours(mask)
    high_importance = contours.smoothed_contours(
        mask, importance_map=np.ones((h, w), dtype=np.float32),
    )

    bg_pts = sum(len(c) for c in background)
    hi_pts = sum(len(c) for c in high_importance)
    assert hi_pts > bg_pts


def test_contour_simplification_reduces_vertex_count():
    """The whole point of switching from a raw pixel-diff border to
    findContours + approxPolyDP is fewer, smoother vertices on a noisy
    boundary. Guard against the epsilon accidentally becoming a no-op.

    Models the real scenario: a mostly-straight region edge with a 1px
    staircase (JPEG-noise-scale), on a region large enough that the
    perimeter-scaled epsilon actually exceeds that noise amplitude — the
    same regime as a real printed region, not an all-noise toy shape.
    """
    h, w = 200, 400
    label_img = np.zeros((h, w), dtype=np.int32)
    top, bottom, left, right = 50, 150, 50, 350
    for x in range(left, right):
        depth = bottom + (1 if (x // 2) % 2 == 0 else 0)  # 1px staircase on one edge
        label_img[top:depth, x] = 1

    mask = (label_img == 1).astype(np.uint8)
    contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    raw_points = sum(len(c) for c in contours)

    simplified_points = 0
    for c in contours:
        epsilon = config.CONTOUR_SIMPLIFY_EPS * cv2.arcLength(c, True)
        simplified_points += len(cv2.approxPolyDP(c, epsilon, True))

    assert raw_points > 20  # the staircase really did add many raw vertices
    assert simplified_points < raw_points * 0.5


def test_line_art_smoke():
    """line_art must return a same-sized white-background RGB canvas, with a
    drawn outline between two regions and no crash on a tiny speck region.
    """
    from app.cache import PaletteEntry

    h, w = 200, 200
    label_img = np.ones((h, w), dtype=np.int32)  # background = cluster 1 (index 2)
    label_img[40:140, 40:140] = 0                # a block = cluster 0 (index 1)
    label_img[60:66, 60:66] = 2                  # a tiny speck = cluster 2 (index 3)

    palette = [
        PaletteEntry(index=1, hex="#5A3CC8", lab=(30.0, 40.0, -50.0), name_ru="фиолетовый"),
        PaletteEntry(index=2, hex="#FAF5EB", lab=(96.0, 0.0, 3.0), name_ru="белый"),
        PaletteEntry(index=3, hex="#FFD21E", lab=(85.0, 5.0, 80.0), name_ru="жёлтый"),
    ]

    canvas = render.line_art(label_img, palette, thickness=2)

    assert canvas.shape == (h, w, 3)
    assert canvas.dtype == np.uint8
    # White background must still be present somewhere (not fully painted over).
    assert np.any(np.all(canvas == 255, axis=-1))
    # Some black outline pixels must have been drawn.
    assert np.any(np.all(canvas == 0, axis=-1))
