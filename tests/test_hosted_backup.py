from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import closing
import sqlite3
import unittest

from deploy.backup import backup_databases


class HostedBackupTests(unittest.TestCase):
    def test_all_tenants_have_independent_complete_backups(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            for user, value in [("a" * 64, "owner"), ("b" * 64, "friend")]:
                directory = root / "user_data" / "users" / user
                directory.mkdir(parents=True)
                for name in ("inventory.sqlite3", "decks.sqlite3"):
                    with closing(sqlite3.connect(directory / name)) as database:
                        database.execute("CREATE TABLE evidence(value TEXT)")
                        database.execute("INSERT INTO evidence VALUES (?)", (value,))
                        database.commit()
            destination = backup_databases(root)
            for user, value in [("a" * 64, "owner"), ("b" * 64, "friend")]:
                for name in ("inventory.sqlite3", "decks.sqlite3"):
                    with closing(sqlite3.connect(destination / "users" / user / name)) as database:
                        self.assertEqual(database.execute("SELECT value FROM evidence").fetchall(), [(value,)])
