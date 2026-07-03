import os
from pathlib import Path

# Directory layout
APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR.parent / "data"
CACHE_DIR = Path(os.getenv("CACHE_DIR", "/tmp/dwhiepaint-cache"))

# Pipeline parameters
MAX_SIDE = int(os.getenv("MAX_SIDE", "2000"))          # longest image side after resize
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "1800"))
CANDIDATE_KS = [8, 12, 16, 20, 24]                      # for auto color count
MIN_REGION_AREA_FRAC = float(os.getenv("MIN_REGION_AREA_FRAC", "0.003"))  # 0.3% of image
DELTA_E_MATCH_THRESHOLD = float(os.getenv("DELTA_E_MATCH_THRESHOLD", "10"))
MIN_K = int(os.getenv("MIN_K", "4"))
MAX_K = int(os.getenv("MAX_K", "32"))

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
