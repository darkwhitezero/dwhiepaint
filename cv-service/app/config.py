import os
from pathlib import Path

# Directory layout
APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR.parent / "data"
CACHE_DIR = Path(os.getenv("CACHE_DIR", "/tmp/dwhiepaint-cache"))

# Redis (async job queue, Phase 6). The cv-service API enqueues jobs and reads
# per-stage progress from here; the ARQ worker runs the heavy pipeline. Ephemeral
# — only job progress/results live here, never user data (that's Postgres).
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
JOB_RESULT_TTL_SECONDS = int(os.getenv("JOB_RESULT_TTL_SECONDS", "3600"))

# Pipeline parameters
MAX_SIDE = int(os.getenv("MAX_SIDE", "2000"))          # longest image side after resize
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "1800"))
MIN_REGION_AREA_FRAC = float(os.getenv("MIN_REGION_AREA_FRAC", "0.003"))  # 0.3% of image
DELTA_E_MATCH_THRESHOLD = float(os.getenv("DELTA_E_MATCH_THRESHOLD", "10"))
MIN_K = int(os.getenv("MIN_K", "4"))
MAX_K = int(os.getenv("MAX_K", "32"))

# Bilateral pre-smoothing (edge-preserving) applied to the source photo before
# Lab conversion, to cut JPEG speckle noise that would otherwise fragment into
# spurious tiny color clusters.
DENOISE_D = int(os.getenv("DENOISE_D", "5"))
DENOISE_SIGMA_COLOR = float(os.getenv("DENOISE_SIGMA_COLOR", "40"))
DENOISE_SIGMA_SPACE = float(os.getenv("DENOISE_SIGMA_SPACE", "40"))

# --- automatic color-count selection (auto-k) -------------------------------
# v2 runs a real mini-segmentation (cluster + regions + merge) per candidate
# on a downsampled working copy, so the search cost stays bounded even with a
# denser candidate grid than the old color-only silhouette pass.
AUTO_K_WORKING_MAX_SIDE = int(os.getenv("AUTO_K_WORKING_MAX_SIDE", "480"))
AUTO_K_CANDIDATES = list(range(6, 31, 2))               # 13 candidates vs. the old 5
AUTO_K_SIL_SAMPLE = int(os.getenv("AUTO_K_SIL_SAMPLE", "3000"))
# Composite score weights: silhouette (color separation) vs. fragmentation
# penalty (too many post-merge regions) vs. dominance penalty (one region
# swallowing most of the image = under-segmentation).
AUTO_K_W_SILHOUETTE = float(os.getenv("AUTO_K_W_SILHOUETTE", "1.0"))
# Softened vs. the MVP: subject-aware min-area (Phase 7) cleans up the
# background, so tolerating more regions no longer means a noisy result — it
# lets auto-k pick enough colors to keep subject detail (eyes, text, stars).
AUTO_K_W_FRAGMENTATION = float(os.getenv("AUTO_K_W_FRAGMENTATION", "0.45"))
AUTO_K_W_DOMINANCE = float(os.getenv("AUTO_K_W_DOMINANCE", "0.6"))
AUTO_K_TARGET_REGIONS = int(os.getenv("AUTO_K_TARGET_REGIONS", "64"))  # comfortable paintable-region count
# Silhouette separation falls monotonically with k, so on its own auto-k always
# picks the fewest colors and starves fine detail (eyes, text, stars). This term
# rewards reaching the target paintable-region count, so k rises until the image
# is richly segmented, then the fragmentation penalty above target reins it in —
# giving a peak near TARGET_REGIONS instead of a floor at MIN_K.
AUTO_K_W_DETAIL = float(os.getenv("AUTO_K_W_DETAIL", "0.55"))
AUTO_K_DOMINANCE_THRESHOLD = float(os.getenv("AUTO_K_DOMINANCE_THRESHOLD", "0.6"))  # top region area fraction

# --- edge-aware superpixel segmentation (Phase 5) ---------------------------
# SLIC oversegmentation replaces per-pixel k-means as the spatial primitive, so
# region boundaries follow real image edges instead of color-only clusters. The
# palette is then k-means over the area-weighted mean-Lab of superpixels, which
# is far more stable and boundary-respecting than clustering raw pixels.
# Low compactness lets superpixels bend to real edges (high compactness makes
# square blocks whose seams show up as staircased region outlines); density is
# high so the grain is fine enough that merged regions hug edges smoothly.
SLIC_COMPACTNESS = float(os.getenv("SLIC_COMPACTNESS", "6.0"))
SLIC_SIGMA = float(os.getenv("SLIC_SIGMA", "1.0"))

# NOTE: an earlier attempt at Problem 2 reserved a k-means seed for a
# near-white "accent" population (white daisies against a warm field). It was
# measured across all seven gallery/test images and fired on ZERO of them:
# plain area-weighted k-means already lands a centroid ~0.6 CIEDE2000 from
# that population, so there was nothing to rescue. The real defect turned out
# to be palette FIDELITY (see PALETTE_MAX_SHIFT_DELTA_E below), not centroid
# placement. Removed rather than left as dead configuration.

# Edge-aware region merging: discount a neighbor's merge score when the shared
# border sits on a real image edge (high Sobel gradient), so small regions
# prefer to merge across weak/blurry borders and are reluctant to cross sharp
# ones. 0 disables the term entirely (pre-existing border-length + CIEDE2000
# behavior only). Independent of SUBJECT_AWARE — merging must behave the same
# whether or not the subject-aware pipeline is enabled.
MERGE_EDGE_WEIGHT = float(os.getenv("MERGE_EDGE_WEIGHT", "1.5"))

# Elongated-region merge bias: a thin, wiggly region (a flower stem fragment,
# a hair strand) is unpaintable even when its raw area clears min_area — the
# label just won't fit and the "region" reads as a scatter of same-color
# specks rather than one paintable shape. Regions whose shape factor
# (perimeter^2 / (4*pi*area), 1.0 for a circle, large for slivers) exceeds
# this threshold get their effective min_area scaled up by
# MERGE_ELONGATION_MIN_AREA_MULT, so they keep merging into a neighbor until
# they've fattened into something a person can actually fill in. 1.0 (mult)
# disables the term entirely (pre-existing behavior, unchanged).
MERGE_ELONGATION_SHAPE_THRESHOLD = float(os.getenv("MERGE_ELONGATION_SHAPE_THRESHOLD", "4.0"))
MERGE_ELONGATION_MIN_AREA_MULT = float(os.getenv("MERGE_ELONGATION_MIN_AREA_MULT", "2.5"))

# Palette legend readability: after building the palette, adjacent (dark→light
# sorted) entries closer than this CIEDE2000 distance are nudged apart along L
# so two different numbers read as visually distinct swatches. Same order of
# magnitude as paints.DIRECT_MATCH_THRESHOLD.
PALETTE_MIN_SEPARATION_DELTA_E = float(os.getenv("PALETTE_MIN_SEPARATION_DELTA_E", "6.0"))
# Hard ceiling on how far that separation may move an entry from its own true
# color. The separated color is what the painted preview and the printed
# legend are filled with, so drift is a lie about the photo — and it must stay
# under the ~2.3 CIEDE2000 just-noticeable-difference. Uncapped, a run of
# near-duplicate colors ratchets: measured on a real landscape, the brightest
# entry drifted +12 L (dE 7.4 from truth). Separation now gives up and leaves
# a collision rather than paint a visibly wrong color.
PALETTE_MAX_SHIFT_DELTA_E = float(os.getenv("PALETTE_MAX_SHIFT_DELTA_E", "2.5"))

# Morphological open/close on the label map before region extraction, to shed
# single-pixel ragged edges left by quantization (kernel in px at working res).
MORPH_KERNEL = int(os.getenv("MORPH_KERNEL", "3"))

# Detail presets tune (superpixel density, palette-size bias, min paintable
# region size) together. The client sends a preset name; "standard" is default.
# k_bias shifts predicted_k so "detailed" gets more colors, "beginner" fewer.
DETAIL_PRESETS = {
    "beginner": {"slic_n_segments": 2000, "min_region_area_frac": 0.010, "k_bias": -4},
    "standard": {"slic_n_segments": 4500, "min_region_area_frac": 0.003, "k_bias": 0},
    "detailed": {"slic_n_segments": 9000, "min_region_area_frac": 0.0012, "k_bias": 4},
}
DEFAULT_DETAIL = os.getenv("DEFAULT_DETAIL", "standard")


def detail_preset(name: str | None) -> dict:
    """Return the tunable bundle for a detail preset, falling back to default."""
    return DETAIL_PRESETS.get(name or DEFAULT_DETAIL, DETAIL_PRESETS["standard"])


# Contour simplification: approxPolyDP epsilon as a fraction of each region's
# perimeter, smoothing pixel-level jaggies from JPEG noise while preserving
# real corners. Capped by an ABSOLUTE pixel value too: on a thin, elongated
# region (e.g. a hair strand), perimeter is large relative to width, so the
# relative term alone can grow past the region's own width and make
# approxPolyDP collapse the two sides into a self-intersecting polygon. The
# absolute cap keeps epsilon small enough to only ever remove few-pixel noise.
# Smoothing is done on the LABEL MAP (see LABEL_SMOOTH_SIGMA), not per-contour:
# a shared boundary must move identically for both neighbors, else independent
# per-region smoothing splits it into two parallel lines. So contour extraction
# only lightly simplifies (drop sub-epsilon noise) and Chaikin defaults to off.
CONTOUR_SIMPLIFY_EPS = float(os.getenv("CONTOUR_SIMPLIFY_EPS", "0.0015"))
CONTOUR_SIMPLIFY_MAX_PX = float(os.getenv("CONTOUR_SIMPLIFY_MAX_PX", "1.5"))
CONTOUR_SMOOTH_ITERS = int(os.getenv("CONTOUR_SMOOTH_ITERS", "0"))
# Finer epsilon fraction used on high-importance contours (subject/edges/faces)
# instead of the coarser CONTOUR_SIMPLIFY_EPS above — see contours._contour_eps_frac.
# Still subject to the same absolute CONTOUR_SIMPLIFY_MAX_PX cap.
CONTOUR_SIMPLIFY_EPS_DETAIL = float(os.getenv("CONTOUR_SIMPLIFY_EPS_DETAIL", "0.0004"))

# Gaussian-argmax smoothing of the final label map: blur each color's
# membership and re-assign each pixel to the strongest nearby color. This
# rounds superpixel-seam staircases while keeping labels discrete AND shared
# boundaries consistent (one boundary, not two). Sigma in px at working res.
LABEL_SMOOTH_SIGMA = float(os.getenv("LABEL_SMOOTH_SIGMA", "2.5"))

# --- subject-aware detail (Phase 7) -----------------------------------------
# Small high-frequency details (eyes, text, stars) get merged away and their
# colors quantized out. A per-pixel importance map — high-contrast edges + the
# rembg subject alpha + face boxes — spatially modulates the minimum paintable
# region size, so detail survives where it matters while flat background is
# aggressively simplified. Master switch; when off the pipeline is uniform.
SUBJECT_AWARE = os.getenv("SUBJECT_AWARE", "1") not in ("0", "false", "False")
REMBG_MODEL = os.getenv("REMBG_MODEL", "u2net")
# Skip matting on images too small to be worth it (short side, px at working res).
SUBJECT_MIN_SIDE = int(os.getenv("SUBJECT_MIN_SIDE", "320"))
# Run rembg on a copy no larger than this (u2net is 320px internally anyway);
# the soft mask is upscaled back. Keeps matting fast on big working images.
REMBG_MAX_SIDE = int(os.getenv("REMBG_MAX_SIDE", "1024"))

# Importance map composition. Baseline everywhere is FLOOR; edges and subject
# add on top, faces get a flat boost. Values are roughly in [FLOOR, ~2].
IMPORTANCE_FLOOR = float(os.getenv("IMPORTANCE_FLOOR", "0.15"))
IMPORTANCE_W_EDGE = float(os.getenv("IMPORTANCE_W_EDGE", "0.85"))
IMPORTANCE_W_SUBJECT = float(os.getenv("IMPORTANCE_W_SUBJECT", "0.6"))
IMPORTANCE_FACE_BOOST = float(os.getenv("IMPORTANCE_FACE_BOOST", "0.7"))
# How wide (fraction of short side) a thin edge is dilated into a protected band.
IMPORTANCE_EDGE_DILATE_FRAC = float(os.getenv("IMPORTANCE_EDGE_DILATE_FRAC", "0.004"))
# When a subject is found, damp edge saliency OUTSIDE it so a genuinely busy
# background doesn't steal the whole detail budget. Kept low so high-contrast
# background decorations (stars, hearts, text) still survive — only flat
# background is simplified (0 = no damping, 1 = full).
IMPORTANCE_BG_EDGE_DAMP = float(os.getenv("IMPORTANCE_BG_EDGE_DAMP", "0.2"))
# On a subject-LESS image the damp term above never runs at all, so a busy
# background (a whole field of flowers, foliage, water ripples) reads as
# uniformly "important" and the per-region min-area collapses to
# MIN_AREA_DETAIL_PX everywhere: hundreds of unpaintable micro-regions (see
# docs/issues/landscape-quality, Problem 1). This applies the same kind of
# damping globally in that case, so texture-only busyness no longer
# monopolizes the whole detail budget. Higher = more aggressive
# simplification of subjectless-image texture (0 = current behavior,
# unchanged).
#
# "Subject-less" is NOT just matte.subject_mask returning None (SUBJECT_AWARE
# off / image too small / rembg unavailable) — verified on a real photo
# (docs/issues/landscape-quality's daisy-field test image) that rembg (u2net)
# almost always returns a *non-None* mask, but on a scene with no single
# salient foreground object that mask is essentially all-zero (mean well
# under 1%) rather than actually None. Both cases mean "no real subject was
# found" and must trigger the same global damping — see
# IMPORTANCE_SUBJECT_MIN_MEAN below.
IMPORTANCE_NO_SUBJECT_EDGE_DAMP = float(os.getenv("IMPORTANCE_NO_SUBJECT_EDGE_DAMP", "0.6"))
# Minimum mean alpha for a rembg mask to count as "a real subject was found".
# Below this, the mask is treated the same as alpha=None (see above).
IMPORTANCE_SUBJECT_MIN_MEAN = float(os.getenv("IMPORTANCE_SUBJECT_MIN_MEAN", "0.02"))

# Map per-region mean importance in [LOW, HIGH] to an ABSOLUTE minimum paintable
# area: low importance → the preset's (large) base area, so flat background
# collapses into big clean regions; high importance → DETAIL_PX, so small
# details (eyes, decorations) survive. DETAIL_PX also acts as the floor that
# still merges sub-detail sparkle noise. Decoupling from a multiplier of the
# large base is what lets both the subject AND crisp background marks survive.
IMPORTANCE_LOW = float(os.getenv("IMPORTANCE_LOW", "0.2"))
IMPORTANCE_HIGH = float(os.getenv("IMPORTANCE_HIGH", "1.0"))
MIN_AREA_DETAIL_PX = int(os.getenv("MIN_AREA_DETAIL_PX", "130"))
MIN_AREA_HARD_FLOOR = int(os.getenv("MIN_AREA_HARD_FLOOR", "40"))

# Upscale small inputs to at least this longest side (px) before processing, so
# tiny photos still have the resolution to carry paintable detail.
UPSCALE_MIN_SIDE = int(os.getenv("UPSCALE_MIN_SIDE", "1400"))

COLOR_DICTIONARY_PATH = DATA_DIR / "colors.json"

# Font with Cyrillic glyphs for the legend (installed via apt in the Dockerfile).
FONT_PATH = os.getenv(
    "FONT_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
)
FONT_PATH_BOLD = os.getenv(
    "FONT_PATH_BOLD", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
)

# Printable page sizes in pixels at 600 dpi (portrait).
PAGE_SIZES_PX = {
    "A4": (4960, 7016),
    "A3": (7016, 9922),
}

CACHE_DIR.mkdir(parents=True, exist_ok=True)
