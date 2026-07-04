import cv2
import numpy as np

from app import config, render


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
