from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]  # .../cgl_api
DATA_DIR = BASE_DIR / "data"

RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
RESULTS_DIR = DATA_DIR / "results"

DEFAULT_N_VIDEOS = 50
DEFAULT_BASELINE_WINDOW = 20

def ensure_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# load .env from project root (parent of cgl_api)
load_dotenv(dotenv_path=BASE_DIR.parent / ".env", override=False)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "").strip()
if not YOUTUBE_API_KEY:
    raise ValueError("YOUTUBE_API_KEY is not set in the environment variables.")
