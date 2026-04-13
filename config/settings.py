import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any, Optional

load_dotenv()

BASE_DIR = Path(__file__).parent.parent

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

ARTIFACTS_DIR = BASE_DIR / "artifacts"
REQUIREMENTS_DIR = ARTIFACTS_DIR / "requirements"
EPICS_DIR = ARTIFACTS_DIR / "epics"
STORIES_DIR = ARTIFACTS_DIR / "stories"
TESTS_DIR = ARTIFACTS_DIR / "tests"

for dir_path in [ARTIFACTS_DIR, REQUIREMENTS_DIR, EPICS_DIR, STORIES_DIR, TESTS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

_MODELS_CONFIG: Optional[Dict[str, Any]] = None


def load_models_config() -> Dict[str, Any]:
    global _MODELS_CONFIG
    if _MODELS_CONFIG is None:
        config_path = BASE_DIR / "config" / "models.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"models.yaml not found at {config_path}")
        with open(config_path, "r") as f:
            _MODELS_CONFIG = yaml.safe_load(f)
    return _MODELS_CONFIG


def get_agent_config(agent_name: str) -> Dict[str, Any]:
    config = load_models_config()
    
    registered = config.get("registered_agents", [])
    if agent_name not in registered:
        raise ValueError(
            f"Agent '{agent_name}' is not registered in models.yaml. "
            f"Registered agents: {registered}"
        )
    
    agents = config.get("agents", {})
    if agent_name not in agents:
        raise ValueError(
            f"Agent '{agent_name}' is registered but has no configuration in models.yaml"
        )
    
    return agents[agent_name]


def get_default_config() -> Dict[str, Any]:
    config = load_models_config()
    return config.get("defaults", {})


def get_registered_agents() -> list:
    config = load_models_config()
    return config.get("registered_agents", [])