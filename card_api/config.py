"""Paths and source constants for the local card catalog."""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = Path(os.environ.get("CARD_DATA_ROOT", PROJECT_ROOT / "data"))
RAW_ROOT = Path(os.environ.get("CARD_RAW_ROOT", DATA_ROOT / "raw" / "malie"))
DATABASE_PATH = Path(
    os.environ.get("CARD_DATABASE_PATH", DATA_ROOT / "card_catalog.sqlite3")
)

MALIE_SOURCE_KEY = "malie-tcgl"
MALIE_SOURCE_NAME = "Malie.io Pokemon TCG Live exports"
MALIE_INDEX_URL = "https://cdn.malie.io/file/malie-io/tcgl/export/index.json"
MALIE_EXPORT_BASE_URL = "https://cdn.malie.io/file/malie-io/tcgl/export/"
DEFAULT_LOCALE = "en-US"
