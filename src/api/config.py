"""
Central configuration.  Import this module before anything that reads
environment variables so that a project-root ``.env`` file is honoured
(real environment variables always win over the file).
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
IS_PRODUCTION = APP_ENV == "production"

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


MODELS_DIR = os.getenv("MODELS_DIR") or str(PROJECT_ROOT / "models")

ACCESS_TOKEN_EXPIRE_MINUTES = env_int("ACCESS_TOKEN_EXPIRE_MINUTES", 60)

# Machine-to-machine key for POST /transactions/score (optional; analyst JWTs also work)
SCORING_API_KEY = os.getenv("SCORING_API_KEY") or None
SCORE_RATE_LIMIT_PER_MIN = env_int("SCORE_RATE_LIMIT_PER_MIN", 600)

LOGIN_MAX_ATTEMPTS = env_int("LOGIN_MAX_ATTEMPTS", 5)
LOGIN_WINDOW_SECONDS = env_int("LOGIN_WINDOW_SECONDS", 900)

# "now"    -> rolling analytics windows end at the current time (production behaviour)
# "latest" -> windows end at the newest transaction (useful for static demo data)
ANALYTICS_ANCHOR = os.getenv("ANALYTICS_ANCHOR", "now").strip().lower()
