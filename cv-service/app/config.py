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

COLOR_DICTIONARY_PATH = DATA_DIR / "colors.json"

CACHE_DIR.mkdir(parents=True, exist_ok=True)
