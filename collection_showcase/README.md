# Read-only collection showcase

This folder is a standalone snapshot of the Pokémon card collection. It does
not connect to the scanner, the catalog database, or the live inventory
database. There are no controls that can add, remove, or change cards.

## Open on Windows

Double-click `Open Collection - Windows.bat`.

You can also double-click `index.html` directly.

## Open on macOS

Double-click `Open Collection - macOS.command`.

If macOS blocks the launcher after downloading it, Control-click it, choose
**Open**, and confirm once. You can also double-click `index.html` directly.

## Notes

- An internet connection is needed to display card artwork from the existing
  Malie image URLs.
- Quantities and card details come from the frozen `inventory_snapshot.js`
  file in this folder.
- Future live inventory changes will not appear until a new snapshot is
  deliberately exported.

## Refreshing the snapshot

From the repository root, run:

```text
python collection_showcase/export_snapshot.py
```

The exporter opens both SQLite databases in read-only mode and rewrites only
the standalone snapshot file.
