import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SQLALCHEMY_DATABASE_URI = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{PROJECT_ROOT / 'accounting.sqlite'}",
)
SQLALCHEMY_TRACK_MODIFICATIONS = False
MAX_CONTENT_LENGTH = 16 * 1024
JSON_SORT_KEYS = False
