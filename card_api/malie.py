"""Download and preserve untouched Malie TCGL formatted exports."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin

from .config import DEFAULT_LOCALE, MALIE_EXPORT_BASE_URL, MALIE_INDEX_URL, RAW_ROOT


Fetch = Callable[[str], bytes]


@dataclass(frozen=True)
class UpdateStatus:
    source_set_id: str
    name: str
    code: str
    status: str
    upstream_hash: str


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Pokemon-TCG-Inventory/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def read_manifest(raw_root: Path = RAW_ROOT) -> dict:
    path = raw_root / "manifest.json"
    if not path.exists():
        return {"schema_version": 1, "sets": {}}
    with path.open("r", encoding="utf-8") as source:
        manifest = json.load(source)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("sets", {}), dict):
        raise ValueError(f"Invalid raw-data manifest: {path}")
    return manifest


def inspect_updates(
    *,
    locale: str = DEFAULT_LOCALE,
    raw_root: Path = RAW_ROOT,
    fetch: Fetch = fetch_bytes,
) -> tuple[bytes, dict, list[UpdateStatus]]:
    index_bytes = fetch(MALIE_INDEX_URL)
    index = json.loads(index_bytes)
    if not isinstance(index, dict) or not isinstance(index.get(locale), dict):
        raise ValueError(f"Malie index has no object for locale {locale!r}")

    manifest = read_manifest(raw_root)
    prior_sets = manifest.get("sets", {})
    statuses: list[UpdateStatus] = []
    for source_set_id, entry in sorted(index[locale].items()):
        if not isinstance(entry, dict):
            statuses.append(UpdateStatus(source_set_id, "", "", "invalid", ""))
            continue
        key = f"{locale}:{source_set_id}"
        prior = prior_sets.get(key, {})
        upstream_hash = str(entry.get("hash", ""))
        local_path = raw_root / str(prior.get("local_path", ""))
        if not prior:
            status = "new"
        elif prior.get("upstream_hash") != upstream_hash:
            status = "updated"
        elif not local_path.is_file():
            status = "missing-local-file"
        else:
            status = "current"
        statuses.append(
            UpdateStatus(
                source_set_id=source_set_id,
                name=str(entry.get("name", "")),
                code=str(entry.get("abbr", "")),
                status=status,
                upstream_hash=upstream_hash,
            )
        )
    return index_bytes, index, statuses


def download_updates(
    *,
    locale: str = DEFAULT_LOCALE,
    raw_root: Path = RAW_ROOT,
    only_sets: set[str] | None = None,
    fetch: Fetch = fetch_bytes,
) -> list[UpdateStatus]:
    """Download changed exports without modifying any previously downloaded JSON."""
    index_bytes, index, statuses = inspect_updates(
        locale=locale, raw_root=raw_root, fetch=fetch
    )
    raw_root.mkdir(parents=True, exist_ok=True)
    manifest = read_manifest(raw_root)
    manifest.setdefault("sets", {})
    checked_at = datetime.now(timezone.utc).isoformat()

    index_sha256 = hashlib.sha256(index_bytes).hexdigest()
    index_relative = Path("indexes") / f"{index_sha256}.json"
    _write_immutable(raw_root / index_relative, index_bytes)

    status_by_id = {item.source_set_id: item for item in statuses}
    for source_set_id, entry in sorted(index[locale].items()):
        if only_sets and source_set_id not in only_sets:
            continue
        status = status_by_id[source_set_id]
        if status.status == "invalid":
            continue
        key = f"{locale}:{source_set_id}"
        if status.status == "current":
            continue

        source_url = urljoin(MALIE_EXPORT_BASE_URL, str(entry["path"]))
        payload = fetch(source_url)
        upstream_hash = str(entry.get("hash", ""))
        if upstream_hash and len(upstream_hash) == 32:
            actual_md5 = hashlib.md5(payload).hexdigest()  # noqa: S324 - upstream integrity format
            if actual_md5.casefold() != upstream_hash.casefold():
                raise ValueError(
                    f"Hash mismatch for {source_set_id}: expected {upstream_hash}, got {actual_md5}"
                )
        sha256 = hashlib.sha256(payload).hexdigest()
        relative_path = Path("sets") / locale / source_set_id / f"{sha256}.json"
        _write_immutable(raw_root / relative_path, payload)
        manifest["sets"][key] = {
            "source_set_id": source_set_id,
            "locale": locale,
            "name": entry.get("name"),
            "abbr": entry.get("abbr"),
            "card_count": entry.get("num"),
            "index_path": entry.get("path"),
            "source_url": source_url,
            "upstream_hash": upstream_hash,
            "sha256": sha256,
            "local_path": relative_path.as_posix(),
            "downloaded_at": checked_at,
        }

    manifest.update(
        {
            "schema_version": 1,
            "source": "malie-tcgl",
            "index_url": MALIE_INDEX_URL,
            "locale": locale,
            "checked_at": checked_at,
            "index_sha256": index_sha256,
            "index_local_path": index_relative.as_posix(),
        }
    )
    _write_json_atomic(raw_root / "manifest.json", manifest)
    return statuses


def statuses_as_dicts(statuses: list[UpdateStatus]) -> list[dict]:
    return [asdict(status) for status in statuses]


def _write_immutable(path: Path, payload: bytes) -> None:
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"Refusing to overwrite different raw data at {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_bytes_atomic(path, payload)


def _write_json_atomic(path: Path, value: dict) -> None:
    payload = (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    _write_bytes_atomic(path, payload)


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as target:
            target.write(payload)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
