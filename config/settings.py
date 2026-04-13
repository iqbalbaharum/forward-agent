import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent

QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-plus")

ARTIFACTS_DIR = BASE_DIR / "artifacts"
REQUIREMENTS_DIR = ARTIFACTS_DIR / "requirements"
EPICS_DIR = ARTIFACTS_DIR / "epics"
STORIES_DIR = ARTIFACTS_DIR / "stories"
TESTS_DIR = ARTIFACTS_DIR / "tests"

for dir_path in [ARTIFACTS_DIR, REQUIREMENTS_DIR, EPICS_DIR, STORIES_DIR, TESTS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)