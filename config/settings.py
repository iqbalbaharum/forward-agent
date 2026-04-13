import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "qwen/qwen2.5-72b-instruct")

ARTIFACTS_DIR = BASE_DIR / "artifacts"
REQUIREMENTS_DIR = ARTIFACTS_DIR / "requirements"
EPICS_DIR = ARTIFACTS_DIR / "epics"
STORIES_DIR = ARTIFACTS_DIR / "stories"
TESTS_DIR = ARTIFACTS_DIR / "tests"

for dir_path in [ARTIFACTS_DIR, REQUIREMENTS_DIR, EPICS_DIR, STORIES_DIR, TESTS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)