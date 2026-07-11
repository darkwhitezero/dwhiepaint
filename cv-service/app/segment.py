"""/segment pipeline: superpixels → palette → merge small → palette + line art."""

from __future__ import annotations

import heapq
from typing import Callable

import cv2
import numpy as np
from skimage.color import deltaE_ciede2000, lab2rgb, rgb2lab

from . import config, importance, render, storage, superpixels, vectorize
from .cache import ImageEntry, PaletteEntry, Segmentation, save_segmentation
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

    # Detail-importance map (subject alpha + edges + faces). It spatially
    # modulates the minimum paintable region size so small details survive where
    # they matter (eyes, text, stars) while flat background collapses into clean
    # regions. Heavy (rembg), so it runs up front under its own stage; None when
    # subject-aware mode is off, which reduces to a uniform min-area.
    report("subject", 0.02)
    imp_map = None
    if config.SUBJECT_AWARE:
        imp_map, _ = importance.importance_map(entry.rgb)

    # Edge-aware quantization: SLIC superpixels + area-weighted palette k-means
    # (the heaviest single stage — superpixel oversegmentation + clustering).
    report("superpixels", 0.14)
    labels, centroids = superpixels.quantize(entry.lab, preset["slic_n_segments"], k)
    actual_k = centroids.shape[0]

    # Despeckle stray single pixels at superpixel seams before splitting regions.
    if actual_k <= 255:
        labels = cv2.medianBlur(labels.astype(np.uint8), 3).astype(np.int32)

    report("merge", 0.52)
    region_id, region_cluster, areas = connected_regions(labels, actual_k)
    base_min_area = max(16, int(preset["min_region_area_frac"] * h * w))
    min_area = (
        _region_min_area(region_id, areas, imp_map, base_min_area)
        if imp_map is not None
        else base_min_area
    )
    # Edge-aware merge bias: computed independently of SUBJECT_AWARE/imp_map so
    # merging behaves the same whether or not the subject-aware pipeline runs.
    gradient_mag = _gradient_magnitude(entry.rgb) if config.MERGE_EDGE_WEIGHT > 0 else None
    cleaned = merge_small_regions(
        region_id, region_cluster, areas, min_area, cluster_lab=centroids,
        gradient_mag=gradient_mag,
    )

    # Round staircased boundaries on the label map itself (not per-contour), so
    # each shared edge stays a single smooth line for both neighbors.
    report("smooth", 0.68)
    cleaned = _smooth_label_map(cleaned, config.LABEL_SMOOTH_SIGMA)

    idx_img, palette = _build_palette(cleaned, entry.rgb)

    seg = Segmentation(k=k, label_img=idx_img, palette=palette, importance_map=imp_map)
    entry.segmentation = seg

    # Three artifacts from the one label map: raster line art (fast on-screen),
    # a painted-preview PNG ("what it'll look like done"), and the canonical
    # scalable SVG line art.
    report("render", 0.78)
    canvas = render.line_art(idx_img, palette, thickness=1, importance_map=imp_map)
    seg.region_map_url = storage.save_rgb_png(entry.image_id, "regions.png", canvas)
    preview = render.painted_preview(idx_img, palette)
    seg.painted_preview_url = storage.save_rgb_png(entry.image_id, "preview_painted.png", preview)

    report("vectorize", 0.9)
    svg = vectorize.to_svg(idx_img, palette, importance_map=imp_map)
    seg.svg_url = storage.save_text(entry.image_id, "regions.svg", svg)

    # Persist to disk so a DIFFERENT process (the API container handling a
    # later /export, when segmentation ran in the worker container) can
    # reconstruct this segmentation instead of 409-ing — see cache.ensure_segmentation.
    save_segmentation(entry.image_id, seg)

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


def _region_min_area(
    region_id: np.ndarray,
    areas: np.ndarray,
    importance_map: np.ndarray,
    base_min_area: int,
) -> np.ndarray:
    """Per-region minimum paintable area from each region's mean importance.

    High-importance regions (subject / edges / faces) get a small threshold so
    tiny details survive the merge; low-importance (flat background) gets a large
    one so noise collapses into big, clean regions. Returns a float array indexed
    by region id, floored so 1px specks can never survive anywhere.
    """
    r = len(areas)
    imp_sum = np.bincount(region_id.ravel(), weights=importance_map.ravel(), minlength=r)
    imp_region = imp_sum / np.maximum(areas, 1.0)

    span = max(1e-6, config.IMPORTANCE_HIGH - config.IMPORTANCE_LOW)
    t = np.clip((imp_region - config.IMPORTANCE_LOW) / span, 0.0, 1.0)
    # t=0 (flat/background) → base_min_area; t=1 (subject/edges) → DETAIL_PX.
    out = base_min_area + t * (config.MIN_AREA_DETAIL_PX - base_min_area)
    return np.maximum(config.MIN_AREA_HARD_FLOOR, out).astype(np.float64)


def _gradient_magnitude(rgb: np.ndarray) -> np.ndarray:
    """Local edge strength (normalized [0,1] Sobel magnitude), used to bias
    region merging away from crossing real image edges (see
    ``merge_small_regions``'s ``gradient_mag``). Deliberately independent of
    ``importance._edge_saliency``: that one widens/blurs edges into a
    protected band for min-area purposes and is gated behind SUBJECT_AWARE;
    this is the raw, un-widened local gradient, needed unconditionally so
    merge behavior doesn't change when subject-aware mode is off.
    """
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(gx, gy)
    hi = float(np.percentile(mag, 98))  # robust max: ignore rare spikes
    if hi <= 1e-6:
        return np.zeros_like(mag)
    return np.clip(mag / hi, 0.0, 1.0)


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


def _adjacency(
    region_id: np.ndarray,
    num_regions: int,
    gradient_mag: np.ndarray | None = None,
) -> tuple[dict[int, dict[int, int]], dict[int, dict[int, float]] | None]:
    """Shared-border length between neighboring regions (4-connectivity), and
    — when ``gradient_mag`` is given — the mean edge-gradient magnitude along
    that same shared border, from the identical pixel-pair pass (no extra
    O(H*W) loop).
    """
    a = np.concatenate([region_id[:, :-1].ravel(), region_id[:-1, :].ravel()])
    b = np.concatenate([region_id[:, 1:].ravel(), region_id[1:, :].ravel()])
    diff = a != b
    lo = np.minimum(a[diff], b[diff])
    hi = np.maximum(a[diff], b[diff])

    # `key` can be astronomically large (up to ~num_regions**2) on a busy image
    # with hundreds of thousands of tiny regions (e.g. pure noise) — np.unique
    # sorts rather than allocating a dense array, so it stays safe regardless.
    key = lo * num_regions + hi
    uniq, inverse, counts = np.unique(key, return_inverse=True, return_counts=True)
    los = (uniq // num_regions).astype(int)
    his = (uniq % num_regions).astype(int)

    adj: dict[int, dict[int, int]] = {}
    for l, hgh, cnt in zip(los, his, counts):
        adj.setdefault(int(l), {})[int(hgh)] = int(cnt)
        adj.setdefault(int(hgh), {})[int(l)] = int(cnt)

    if gradient_mag is None:
        return adj, None

    # Mean of the two pixels straddling each border pixel-pair, aggregated per
    # region-pair the same way border length is above. Bincount over `inverse`
    # (range [0, len(uniq))), NOT over `key` itself — key's range scales with
    # num_regions**2 and would blow up bincount's dense allocation.
    ga = np.concatenate([gradient_mag[:, :-1].ravel(), gradient_mag[:-1, :].ravel()])
    gb = np.concatenate([gradient_mag[:, 1:].ravel(), gradient_mag[1:, :].ravel()])
    g = ((ga + gb) / 2.0)[diff]
    sums = np.bincount(inverse, weights=g, minlength=len(uniq))
    grad_adj: dict[int, dict[int, float]] = {}
    for idx, (l, hgh, cnt) in enumerate(zip(los, his, counts)):
        mean_g = float(sums[idx] / cnt) if cnt else 0.0
        grad_adj.setdefault(int(l), {})[int(hgh)] = mean_g
        grad_adj.setdefault(int(hgh), {})[int(l)] = mean_g
    return adj, grad_adj


def _region_perimeters(region_id: np.ndarray, r: int) -> np.ndarray:
    """Approximate each region's boundary length (pixel-edge count) via a
    single O(H*W) 4-neighbor comparison pass — cheap and consistent, unlike
    per-region ``cv2.findContours`` over potentially thousands of regions.
    Used only for the elongation shape factor below, not for rendering.
    """
    h, w = region_id.shape
    OUT = np.array(-2, dtype=region_id.dtype)  # sentinel: always "different"
    padded = np.full((h + 2, w + 2), OUT, dtype=region_id.dtype)
    padded[1:-1, 1:-1] = region_id
    center = padded[1:-1, 1:-1]
    perim = np.zeros(r, dtype=np.float64)
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        neighbor = padded[1 + dy:1 + dy + h, 1 + dx:1 + dx + w]
        valid = (neighbor != center) & (center >= 0)
        perim += np.bincount(center[valid].ravel(), minlength=r)
    return perim


def _elongation_multiplier(region_id: np.ndarray, areas: np.ndarray) -> np.ndarray | None:
    """Per-region min-area multiplier for badly-elongated slivers (a flower-
    stem fragment, a hair strand) that stay unpaintable even once their raw
    area clears ``min_area`` — the shape is too thin to hold a number, and it
    visually reads as a scatter of same-color specks rather than one region
    (docs/issues/landscape-quality, Problem 1). Uses an isoperimetric shape
    factor (perimeter^2 / (4*pi*area): 1.0 for a circle, large for slivers)
    from the approximate boundary pass above. Returns None when the feature
    is off (``MERGE_ELONGATION_MIN_AREA_MULT <= 1.0``), so callers can skip
    the extra O(H*W) pass and the merge stays byte-identical to before this
    existed.
    """
    mult = config.MERGE_ELONGATION_MIN_AREA_MULT
    if mult <= 1.0:
        return None
    r = len(areas)
    perim = _region_perimeters(region_id, r)
    shape_factor = perim ** 2 / np.maximum(4.0 * np.pi * areas, 1e-6)
    out = np.ones(r, dtype=np.float64)
    out[shape_factor > config.MERGE_ELONGATION_SHAPE_THRESHOLD] = mult
    return out


def merge_small_regions(
    region_id: np.ndarray,
    region_cluster: np.ndarray,
    areas: np.ndarray,
    min_area: int | float | np.ndarray,
    cluster_lab: np.ndarray | None = None,
    gradient_mag: np.ndarray | None = None,
) -> np.ndarray:
    """Absorb every region below its minimum area into a well-matched neighbor.

    Public (reused by ``analyze._auto_k``). Picking "largest shared border"
    alone can merge a sliver into a visually distant neighbor when two
    borders are comparable in length (e.g. a thin hair strand between two
    similarly-sized regions). When ``cluster_lab`` (per-cluster Lab
    centroids, e.g. ``KMeans.cluster_centers_``) is given, the border score
    is discounted by how far the neighbor's color is (CIEDE2000) — among
    comparable borders this prefers the perceptually closer-colored neighbor.
    When ``gradient_mag`` (full-image HxW Sobel-magnitude, see
    ``_gradient_magnitude``) is also given, the score is further discounted by
    the mean edge strength along the shared border — a small region prefers to
    merge across a weak/blurry border over a crisp real edge, at equal color
    distance and border length.

    ``min_area`` may be a scalar (uniform threshold) or a per-region array
    indexed by region id (Phase 7 subject-aware detail: keep small important
    regions, merge unimportant ones harder). A merged region inherits the more
    permissive (smaller) threshold of its members, so a detail sitting next to
    background isn't merged away on the next pass.

    Returns an HxW map of (merged) cluster labels.
    """
    r = len(areas)
    parent = list(range(r))
    size = areas.tolist()
    cluster = region_cluster.tolist()
    adj, grad_adj = _adjacency(region_id, r, gradient_mag)

    scalar = np.isscalar(min_area)
    thr = None if scalar else np.asarray(min_area, dtype=np.float64).copy()

    # Elongated slivers need a higher effective threshold than their raw area
    # alone would suggest — converts the threshold to a per-region array only
    # when the feature is actually enabled (see _elongation_multiplier).
    elong_mult = _elongation_multiplier(region_id, areas)
    if elong_mult is not None:
        if scalar:
            thr = np.full(r, float(min_area), dtype=np.float64)
            scalar = False
        thr *= elong_mult

    def region_thr(reg: int) -> float:
        return float(min_area) if scalar else float(thr[reg])

    # Precompute pairwise CIEDE2000 between cluster centroids once (k is small,
    # typically 8-32) rather than a fresh distance calc on every scorer call
    # inside the merge heap loop below.
    dist_matrix = None
    if cluster_lab is not None:
        kk = cluster_lab.shape[0]
        a_lab = np.repeat(cluster_lab, kk, axis=0)
        b_lab = np.tile(cluster_lab, (kk, 1))
        dist_matrix = deltaE_ciede2000(a_lab, b_lab).reshape(kk, kk)

    def neighbor_score(reg: int, n: int, border: int) -> float:
        if cluster_lab is None:
            return float(border)
        dist = float(dist_matrix[cluster[reg], cluster[n]])
        score = border / (1.0 + dist)
        if grad_adj is not None:
            grad = grad_adj.get(reg, {}).get(n, 0.0)
            score /= 1.0 + config.MERGE_EDGE_WEIGHT * grad
        return score

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
        if area >= region_thr(reg):
            if scalar:
                break  # smallest active region already large enough → all are
            continue  # per-region: a larger region may still be below its own
        neighbors = adj.get(reg)
        if not neighbors:
            continue  # isolated region, nothing to merge into

        best_n = max(neighbors, key=lambda n: neighbor_score(reg, n, neighbors[n]))
        nb = find(best_n)
        if nb == reg:
            continue

        parent[reg] = nb
        size[nb] += size[reg]
        if not scalar:
            thr[nb] = min(thr[nb], thr[reg])
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


def _separate_similar_colors(labs: list[np.ndarray]) -> list[np.ndarray]:
    """Nudge visually-too-similar ADJACENT palette entries (already sorted
    dark→light by the caller) apart along L, so two different numbers read as
    distinct swatches on the legend/painted preview.

    Single left-to-right sweep: each entry is pushed lighter only until it
    clears CIEDE2000 separation from the PREVIOUS (already-finalized, never
    revisited) entry. This is simpler and more stable than an all-pairs
    repulsion pass — no oscillation, terminates in bounded steps — and is
    sufficient since near-duplicate colors from k-means are almost always
    adjacent once sorted by lightness. Only the DISPLAYED color changes; the
    segmentation (which pixels belong to which region) is already final by
    this point in the pipeline.
    """
    if len(labs) < 2:
        return labs
    out = [lab.copy() for lab in labs]
    threshold = config.PALETTE_MIN_SEPARATION_DELTA_E
    step, max_iters = 1.0, 20
    for i in range(1, len(out)):
        prev, cur = out[i - 1], out[i]
        for _ in range(max_iters):
            d = float(deltaE_ciede2000(prev.reshape(1, 3), cur.reshape(1, 3))[0])
            if d >= threshold:
                break
            cur[0] = np.clip(cur[0] + step, 0.0, 100.0)
        out[i] = cur
    return out


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

    labs = [rgb2lab(mean_rgb.reshape(1, 1, 3) / 255.0).reshape(3) for _, mean_rgb in means]
    labs = _separate_similar_colors(labs)

    remap = np.full(int(present.max()) + 1, -1, dtype=np.int32)
    palette: list[PaletteEntry] = []
    for new_idx, ((old_c, _), lab) in enumerate(zip(means, labs)):
        remap[old_c] = new_idx
        rgb_f = np.clip(lab2rgb(lab.reshape(1, 1, 3)).reshape(3), 0.0, 1.0)
        rgb_u8 = np.round(rgb_f * 255).astype(int)
        hex_str = "#{:02X}{:02X}{:02X}".format(*rgb_u8)
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
