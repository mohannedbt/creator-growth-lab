from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]  # .../cgl_api
DATA_DIR = BASE_DIR / "data"

RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
RESULTS_DIR = DATA_DIR / "results"

DEFAULT_N_VIDEOS = 30
DEFAULT_BASELINE_WINDOW = 20

def ensure_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# load .env from project root (parent of cgl_api)
# NOTE: override=True so local .env wins over any stale machine/user env vars.
load_dotenv(dotenv_path=BASE_DIR.parent / ".env", override=True)

def _clean_env_value(value: str) -> str:
    return (value or "").strip().strip('"').strip("'")

# Be forgiving: users often paste keys with surrounding quotes in .env
YOUTUBE_API_KEY = _clean_env_value(os.getenv("YOUTUBE_API_KEY", ""))
if not YOUTUBE_API_KEY:
    raise ValueError("YOUTUBE_API_KEY is not set in the environment variables.")

GEMINI_API_KEY = _clean_env_value(os.getenv("GEMINI_API_KEY", ""))
