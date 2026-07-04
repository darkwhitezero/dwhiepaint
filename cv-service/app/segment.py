"""/segment pipeline: k-means → connected regions → merge small → palette + line art."""

from __future__ import annotations

import heapq

import cv2
import numpy as np
from skimage.color import rgb2lab
from sklearn.cluster import MiniBatchKMeans

from . import config, render, storage
from .cache import ImageEntry, PaletteEntry, Segmentation
from .color_naming import name_for_lab


def segment(entry: ImageEntry, k: int) -> tuple[Segmentation, str]:
    """Cluster into k colors, clean regions, name the palette, render line art.

    Returns (segmentation, region_map_url).
    """
    k = int(np.clip(k, config.MIN_K, config.MAX_K))
    h, w = entry.height, entry.width

    lab_pixels = entry.lab.reshape(-1, 3)
    km = MiniBatchKMeans(n_clusters=k, random_state=42, n_init=3, batch_size=2048)
    labels = km.fit_predict(lab_pixels).astype(np.int32).reshape(h, w)

    # Despeckle isolated pixels before splitting into spatial regions.
    if k <= 255:
        labels = cv2.medianBlur(labels.astype(np.uint8), 3).astype(np.int32)

    region_id, region_cluster, areas = connected_regions(labels, k)
    min_area = max(16, int(config.MIN_REGION_AREA_FRAC * h * w))
    cleaned = merge_small_regions(
        region_id, region_cluster, areas, min_area, cluster_lab=km.cluster_centers_,
    )

    idx_img, palette = _build_palette(cleaned, entry.rgb)

    seg = Segmentation(k=k, label_img=idx_img, palette=palette)
    entry.segmentation = seg

    canvas = render.line_art(idx_img, palette, thickness=1)
    region_map_url = storage.save_rgb_png(entry.image_id, "regions.png", canvas)
    return seg, region_map_url


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
