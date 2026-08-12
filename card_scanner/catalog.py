"""Local printed-code catalog used to constrain noisy OCR candidates."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def set_catalog() -> dict[str, dict]:
    root = Path(__file__).resolve().parent
    records: dict[str, dict] = {}
    try:
        payload = json.loads((root / "set_catalog.json").read_text(encoding="utf-8"))
        for code in payload.get("codes", []):
            value = str(code).strip().upper()
            if value:
                records[value] = {"code": value}
    except (OSError, json.JSONDecodeError, TypeError):
        pass

    try:
        aliases = json.loads((root / "set_aliases.json").read_text(encoding="utf-8"))
        for code, details in aliases.items():
            value = str(code).strip().upper()
            if value and isinstance(details, dict):
                records.setdefault(value, {"code": value}).update(details)
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return records


def known_set_codes() -> frozenset[str]:
    return frozenset(set_catalog())
