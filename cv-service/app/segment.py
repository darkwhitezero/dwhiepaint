"""/segment pipeline: superpixels → palette → merge small → palette + line art."""

from __future__ import annotations

import heapq
from typing import Callable

import cv2
import numpy as np
from skimage.color import rgb2lab

from . import config, render, storage, superpixels, vectorize
from .cache import ImageEntry, PaletteEntry, Segmentation
from .color_naming import name_for_lab

# A progress reporter: (stage_name, fraction_complete_in_[0,1]) -> None. Used by
# the async worker to stream per-stage progress to Redis; the sync path passes
# nothing and the calls are no-ops.
ProgressFn = Callable[[str, float], None]


def _noop(stage: str, frac: float) -> None:  # pragma: no cover - trivial
    pass


def segment(
    entry: ImageEntry,
    k: int,
    detail: str | None = None,
    progress: ProgressFn | None = None,
) -> tuple[Segmentation, str]:
    """Edge-aware segmentation → clean regions → name palette → render line art.

    Quantizes via SLIC superpixels + area-weighted palette k-means (see
    ``superpixels``), then merges below-minimum regions and renders. The
    ``detail`` preset tunes superpixel density and the minimum paintable
    region size together. ``progress`` (if given) is called at each stage
    boundary with a rising fraction, so an async caller can stream status.
    Returns (segmentation, region_map_url).
    """
    report = progress or _noop
    preset = config.detail_preset(detail)
    k = int(np.clip(k, config.MIN_K, config.MAX_K))
    h, w = entry.height, entry.width

    # Edge-aware quantization: SLIC superpixels + area-weighted palette k-means
    # (the heaviest single stage — superpixel oversegmentation + clustering).
    report("superpixels", 0.05)
    labels, centroids = superpixels.quantize(entry.lab, preset["slic_n_segments"], k)
    actual_k = centroids.shape[0]

    # Despeckle stray single pixels at superpixel seams before splitting regions.
    if actual_k <= 255:
        labels = cv2.medianBlur(labels.astype(np.uint8), 3).astype(np.int32)

    report("merge", 0.5)
    region_id, region_cluster, areas = connected_regions(labels, actual_k)
    min_area = max(16, int(preset["min_region_area_frac"] * h * w))
    cleaned = merge_small_regions(
        region_id, region_cluster, areas, min_area, cluster_lab=centroids,
    )

    # Round staircased boundaries on the label map itself (not per-contour), so
    # each shared edge stays a single smooth line for both neighbors.
    report("smooth", 0.68)
    cleaned = _smooth_label_map(cleaned, config.LABEL_SMOOTH_SIGMA)

    idx_img, palette = _build_palette(cleaned, entry.rgb)

    seg = Segmentation(k=k, label_img=idx_img, palette=palette)
    entry.segmentation = seg

    # Three artifacts from the one label map: raster line art (fast on-screen),
    # a painted-preview PNG ("what it'll look like done"), and the canonical
    # scalable SVG line art.
    report("render", 0.78)
    canvas = render.line_art(idx_img, palette, thickness=1)
    seg.region_map_url = storage.save_rgb_png(entry.image_id, "regions.png", canvas)
    preview = render.painted_preview(idx_img, palette)
    seg.painted_preview_url = storage.save_rgb_png(entry.image_id, "preview_painted.png", preview)

    report("vectorize", 0.9)
    svg = vectorize.to_svg(idx_img, palette)
    seg.svg_url = storage.save_text(entry.image_id, "regions.svg", svg)

    report("done", 1.0)
    return seg, seg.region_map_url


def _smooth_label_map(labels: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian-argmax smoothing: blur each present label's membership and
    re-assign every pixel to the strongest nearby label. Rounds boundaries
    consistently for both sides of every shared edge (a running argmax keeps
    it memory-light — no k-deep stack).
    """
    present = np.unique(labels)
    if sigma <= 0 or len(present) < 2:
        return labels
    best = np.zeros(labels.shape, dtype=np.float32)
    out = np.full(labels.shape, present[0], dtype=labels.dtype)
    for c in present:
        m = cv2.GaussianBlur((labels == c).astype(np.float32), (0, 0), sigma)
        win = m > best
        best[win] = m[win]
        out[win] = c
    return out


def connected_regions(
    labels: np.ndarray, k: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Split each color cluster into 4-connected components with global ids.

    Public (reused by ``analyze._auto_k`` to score candidate k's on an actual
    mini-segmentation rather than color separation alone).
    """
    h, w = labels.shape
    region_id = np.full((h, w), -1, dtype=np.int64)
    region_cluster: list[int] = []
    counter = 0

    for c in range(k):
        mask = (labels == c).astype(np.uint8)
        if not mask.any():
            continue
        n, cc = cv2.connectedComponents(mask, connectivity=4)
        comp_pixels = cc > 0
        region_id[comp_pixels] = cc[comp_pixels] - 1 + counter
        region_cluster.extend([c] * (n - 1))
        counter += n - 1

    areas = np.bincount(region_id.ravel(), minlength=counter).astype(np.float64)
    return region_id, np.asarray(region_cluster, dtype=np.int32), areas


def _adjacency(region_id: np.ndarray, num_regions: int) -> dict[int, dict[int, int]]:
    """Shared-border length between neighboring regions (4-connectivity)."""
    a = np.concatenate([region_id[:, :-1].ravel(), region_id[:-1, :].ravel()])
    b = np.concatenate([region_id[:, 1:].ravel(), region_id[1:, :].ravel()])
    diff = a != b
    lo = np.minimum(a[diff], b[diff])
    hi = np.maximum(a[diff], b[diff])

    key = lo * num_regions + hi
    uniq, counts = np.unique(key, return_counts=True)
    los = (uniq // num_regions).astype(int)
    his = (uniq % num_regions).astype(int)

    adj: dict[int, dict[int, int]] = {}
    for l, hgh, cnt in zip(los, his, counts):
        adj.setdefault(int(l), {})[int(hgh)] = int(cnt)
        adj.setdefault(int(hgh), {})[int(l)] = int(cnt)
    return adj


def merge_small_regions(
    region_id: np.ndarray,
    region_cluster: np.ndarray,
    areas: np.ndarray,
    min_area: int,
    cluster_lab: np.ndarray | None = None,
) -> np.ndarray:
    """Absorb every region below min_area into a well-matched neighbor.

    Public (reused by ``analyze._auto_k``). Picking "largest shared border"
    alone can merge a sliver into a visually distant neighbor when two
    borders are comparable in length (e.g. a thin hair strand between two
    similarly-sized regions). When ``cluster_lab`` (per-cluster Lab
    centroids, e.g. ``KMeans.cluster_centers_``) is given, the border score
    is discounted by how far the neighbor's color is — among comparable
    borders this prefers the perceptually closer-colored neighbor.

    Returns an HxW map of (merged) cluster labels.
    """
    r = len(areas)
    parent = list(range(r))
    size = areas.tolist()
    cluster = region_cluster.tolist()
    adj = _adjacency(region_id, r)

    def neighbor_score(reg: int, n: int, border: int) -> float:
        if cluster_lab is None:
            return float(border)
        dist = float(np.linalg.norm(cluster_lab[cluster[reg]] - cluster_lab[cluster[n]]))
        return border / (1.0 + dist)

    def find(x: int) -> int:
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    heap = [(size[i], i) for i in range(r)]
    heapq.heapify(heap)

    while heap:
        area, reg = heapq.heappop(heap)
        if find(reg) != reg or area != size[reg]:
            continue  # stale entry
        if area >= min_area:
            break  # smallest active region already large enough
        neighbors = adj.get(reg)
        if not neighbors:
            continue  # isolated region, nothing to merge into

        best_n = max(neighbors, key=lambda n: neighbor_score(reg, n, neighbors[n]))
        nb = find(best_n)
        if nb == reg:
            continue

        parent[reg] = nb
        size[nb] += size[reg]
        for n, border in neighbors.items():
            rn = find(n)
            if rn == nb:
                continue
            adj[nb][rn] = adj[nb].get(rn, 0) + border
            adj[rn][nb] = adj[rn].get(nb, 0) + border
            adj[rn].pop(reg, None)
        adj[nb].pop(reg, None)
        adj[reg] = {}
        heapq.heappush(heap, (size[nb], nb))

    root_cluster = np.array([cluster[find(i)] for i in range(r)], dtype=np.int32)
    return root_cluster[region_id]


def _build_palette(
    cleaned: np.ndarray, rgb: np.ndarray
) -> tuple[np.ndarray, list[PaletteEntry]]:
    """Reindex present clusters (dark→light) and name each color."""
    present = np.unique(cleaned)

    means: list[tuple[int, np.ndarray]] = []
    for c in present:
        mean_rgb = rgb[cleaned == c].reshape(-1, 3).mean(axis=0)
        means.append((int(c), mean_rgb))

    # Order legend from dark to light for readability.
    means.sort(key=lambda cm: cm[1].mean())

    remap = np.full(int(present.max()) + 1, -1, dtype=np.int32)
    palette: list[PaletteEntry] = []
    for new_idx, (old_c, mean_rgb) in enumerate(means):
        remap[old_c] = new_idx
        rgb_u8 = np.clip(np.round(mean_rgb), 0, 255).astype(int)
        hex_str = "#{:02X}{:02X}{:02X}".format(*rgb_u8)
        lab = rgb2lab(mean_rgb.reshape(1, 1, 3) / 255.0).reshape(3)
        name_ru, name_en = name_for_lab(lab)
        palette.append(
            PaletteEntry(
                index=new_idx + 1,
                hex=hex_str,
                lab=(float(lab[0]), float(lab[1]), float(lab[2])),
                name_ru=name_ru,
                name_en=name_en,
            )
        )

    idx_img = remap[cleaned]
    return idx_img, palette
