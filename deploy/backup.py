"""Consistent SQLite snapshots of local and hosted collection saves."""

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3


def backup_databases(root: Path) -> Path:
    data = root / "user_data"
    destination = data / "scheduled-backups" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination.mkdir(parents=True, mode=0o700)
    directories = [data]
    users = data / "users"
    if users.exists():
        directories.extend(path for path in sorted(users.iterdir())
                           if re.fullmatch(r"[0-9a-f]{64}", path.name)
                           and path.is_dir() and not path.is_symlink())
    count = 0
    for directory in directories:
        for name in ("inventory.sqlite3", "decks.sqlite3"):
            database = directory / name
            if not database.is_file():
                continue
            target_path = destination / database.relative_to(data)
            target_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as source:
                with closing(sqlite3.connect(target_path)) as target:
                    source.backup(target)
                    if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise RuntimeError(f"Backup integrity check failed: {target_path}")
            count += 1
    if not count:
        raise RuntimeError("No collection databases found to back up.")
    print(f"Verified {count} collection database backups: {destination}")
    return destination


if __name__ == "__main__":
    backup_databases(Path(__file__).resolve().parents[1])
