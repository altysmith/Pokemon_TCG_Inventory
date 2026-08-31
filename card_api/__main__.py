"""Command-line entry point for card catalog update, import, and serving."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import DATABASE_PATH, DEFAULT_LOCALE, RAW_ROOT
from .database import CatalogDatabase
from .importer import import_downloaded
from .malie import download_updates, inspect_updates, statuses_as_dicts


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Pokemon TCG card database")
    parser.add_argument("--database", type=Path, default=DATABASE_PATH)
    parser.add_argument("--raw-root", type=Path, default=RAW_ROOT)
    subparsers = parser.add_subparsers(dest="command", required=True)

    update = subparsers.add_parser("update", help="Check or download Malie exports")
    update.add_argument("--locale", default=DEFAULT_LOCALE)
    update.add_argument("--download", action="store_true")
    update.add_argument("--set", action="append", dest="sets")

    importer = subparsers.add_parser("import", help="Import preserved raw files into SQLite")
    importer.add_argument("--set", action="append", dest="sets")

    sync = subparsers.add_parser("sync", help="Download changed files, then import them")
    sync.add_argument("--locale", default=DEFAULT_LOCALE)
    sync.add_argument("--set", action="append", dest="sets")

    serve = subparsers.add_parser("serve", help="Run the private local FastAPI service")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8770)

    subparsers.add_parser("init", help="Create an empty catalog database")
    args = parser.parse_args()
    selected = set(args.sets) if getattr(args, "sets", None) else None

    if args.command == "update":
        if args.download:
            statuses = download_updates(
                locale=args.locale, raw_root=args.raw_root, only_sets=selected
            )
        else:
            _index_bytes, _index, statuses = inspect_updates(
                locale=args.locale, raw_root=args.raw_root
            )
        print(json.dumps(statuses_as_dicts(statuses), indent=2, ensure_ascii=False))
    elif args.command == "import":
        result = import_downloaded(
            database_path=args.database, raw_root=args.raw_root, only_sets=selected
        )
        print(json.dumps(result.__dict__, indent=2))
    elif args.command == "sync":
        download_updates(locale=args.locale, raw_root=args.raw_root, only_sets=selected)
        result = import_downloaded(
            database_path=args.database, raw_root=args.raw_root, only_sets=selected
        )
        print(json.dumps(result.__dict__, indent=2))
    elif args.command == "serve":
        import uvicorn

        from .api import create_app

        uvicorn.run(create_app(args.database), host=args.host, port=args.port)
    elif args.command == "init":
        CatalogDatabase(args.database).initialize()
        print(f"Initialized {args.database}")


if __name__ == "__main__":
    main()
