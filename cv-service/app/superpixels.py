"""Edge-aware quantization: SLIC superpixels + area-weighted palette k-means.

Replaces the old per-pixel k-means as the spatial primitive of segmentation.
SLIC oversegments the image into superpixels that hug real edges; the palette
is then k-means over the area-weighted mean-Lab of those superpixels. Clustering
superpixel means (a few thousand points) instead of every pixel is both far
faster and far more stable, and — because each superpixel already respects
edges — the resulting label map has clean boundaries instead of the ragged,
noise-driven ones per-pixel clustering produced.
"""

from __future__ import annotations

import numpy as np
from skimage.color import deltaE_ciede2000
from skimage.segmentation import slic
from sklearn.cluster import KMeans, kmeans_plusplus

from . import config


def oversegment(lab: np.ndarray, n_segments: int) -> np.ndarray:
    """SLIC superpixels over a Lab image → HxW int label map (0-based).

    The image is already in Lab, so ``convert2lab=False`` — SLIC works in Lab
    natively and we must not let it re-convert.
    """
    return slic(
        lab,
        n_segments=max(1, n_segments),
        compactness=config.SLIC_COMPACTNESS,
        sigma=config.SLIC_SIGMA,
        channel_axis=-1,
        convert2lab=False,
        start_label=0,
    ).astype(np.int32)


def superpixel_means(lab: np.ndarray, sp: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return (mean_lab [S,3], area [S]) per superpixel via weighted bincount."""
    n_sp = int(sp.max()) + 1
    flat = sp.ravel()
    area = np.bincount(flat, minlength=n_sp).astype(np.float64)
    safe = np.maximum(area, 1.0)
    means = np.empty((n_sp, 3), dtype=np.float64)
    for c in range(3):
        means[:, c] = np.bincount(flat, weights=lab[:, :, c].ravel(), minlength=n_sp) / safe
    return means, area


def _accent_seed_lab(means: np.ndarray, area: np.ndarray, k: int) -> np.ndarray | None:
    """Find a large, visually extreme (near-white) superpixel population that
    plain area-weighted k-means would likely dilute into a warmer neighbor —
    e.g. white daisies against a warm sunset field losing their contrast
    (docs/issues/landscape-quality, Problem 2) — and return its area-weighted
    mean Lab to seed a reserved centroid. Returns None (no seeding) when the
    feature is off, no such population exists, it's too small to be a real
    accent rather than a stray highlight, or a plain fit would already land a
    centroid near it (nothing to fix).
    """
    if not config.PALETTE_ACCENT_SEEDING or k < 2:
        return None

    L, a, b = means[:, 0], means[:, 1], means[:, 2]
    chroma = np.sqrt(a ** 2 + b ** 2)
    near_white = (L >= config.PALETTE_ACCENT_L_MIN) & (chroma <= config.PALETTE_ACCENT_CHROMA_MAX)
    if not near_white.any():
        return None

    total_area = float(area.sum())
    accent_area = float(area[near_white].sum())
    if total_area <= 0 or accent_area / total_area < config.PALETTE_ACCENT_MIN_AREA_FRAC:
        return None

    accent_lab = np.average(means[near_white], axis=0, weights=area[near_white])

    # Would an unseeded fit already place a centroid near the accent? Then
    # there's nothing to fix — only intervene when it would genuinely dilute.
    baseline = KMeans(n_clusters=k, random_state=42, n_init=3)
    baseline.fit(means, sample_weight=area)
    dists = deltaE_ciede2000(
        np.repeat(accent_lab.reshape(1, 3), k, axis=0), baseline.cluster_centers_,
    )
    if float(dists.min()) < config.PALETTE_ACCENT_DELTA_E:
        return None

    return accent_lab


def palette_from_superpixels(
    lab: np.ndarray, sp: np.ndarray, k: int
) -> tuple[np.ndarray, np.ndarray]:
    """Superpixel-derived palette, then PER-PIXEL assignment to it.

    The palette is k-means over the area-weighted mean-Lab of superpixels —
    stable and representative (large flat areas don't drown out their neighbors,
    tiny superpixels don't over-count). But labels are assigned per *pixel* to
    the nearest palette color, so region boundaries land on true image edges at
    pixel precision instead of the coarse superpixel grid (whose ~grain-sized
    seams would otherwise staircase every outline). Returns (label_map [H,W],
    centroids [k,3] Lab); k is clamped to the superpixel count.

    When a near-white accent population would otherwise be diluted away (see
    ``_accent_seed_lab``), one centroid is seeded at its mean and the rest via
    weighted k-means++ (``n_init=1`` since the seed is deterministic); k stays
    unchanged, one slot is just reserved. Otherwise this is the exact prior
    ``KMeans(random_state=42, n_init=3)`` call, byte-for-byte.
    """
    means, area = superpixel_means(lab, sp)
    n_sp = means.shape[0]
    k = int(np.clip(k, 2, n_sp))

    accent_lab = _accent_seed_lab(means, area, k)
    if accent_lab is not None:
        seeds, _ = kmeans_plusplus(means, k - 1, sample_weight=area, random_state=42)
        init = np.vstack([seeds, accent_lab.reshape(1, 3)])
        km = KMeans(n_clusters=k, init=init, n_init=1, random_state=42)
    else:
        km = KMeans(n_clusters=k, random_state=42, n_init=3)
    km.fit(means, sample_weight=area)
    centroids = km.cluster_centers_

    label_map = km.predict(lab.reshape(-1, 3)).astype(np.int32).reshape(lab.shape[:2])
    return label_map, centroids


def quantize(lab: np.ndarray, n_segments: int, k: int) -> tuple[np.ndarray, np.ndarray]:
    """Full edge-aware quantization: SLIC then palette k-means.

    Returns (label_map [H,W] of palette indices, centroids [k,3] Lab).
    """
    sp = oversegment(lab, n_segments)
    return palette_from_superpixels(lab, sp, k)
