import os

import yaml
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Allow override via environment variable, otherwise default to configs/default.yaml
config_filename = os.getenv("RECALL_CONFIG", "configs/default.yaml")
CONFIG_PATH = os.path.join(BASE_DIR, config_filename)


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


_config = load_config()

# Agent settings
MAX_STEPS = _config.get("agent", {}).get("max_steps", 30)
FALLBACK_COMPACTION_LIMIT = _config.get("agent", {}).get("fallback_compaction_limit", 60000)
COMPACTION_TOKEN_FRACTION = _config.get("agent", {}).get("compaction_token_fraction", 0.75)
DEFAULT_MODEL = _config.get("agent", {}).get("default_model", "haiku-4.5")
COMPACTION_MODEL = _config.get("agent", {}).get("compaction_model", "gemini/gemini-3.1-flash-lite")

# Paths
RUNS_DIR = os.path.join(BASE_DIR, _config.get("paths", {}).get("runs_dir", "runs"))
SYSTEM_PROMPT_PATH = os.path.join(
    BASE_DIR, _config.get("paths", {}).get("system_prompt_file", "prompts/system_prompt.txt")
)
COMPACTION_PROMPT_PATH = os.path.join(
    BASE_DIR,
    _config.get("paths", {}).get("compaction_prompt_file", "prompts/compaction_prompt.txt"),
)


def get_system_prompt() -> str:
    with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def get_compaction_prompt() -> str:
    with open(COMPACTION_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()
