import tempfile
import unittest
import uuid
from pathlib import Path

from runtime_guard import RuntimeLock


class RuntimeLockTests(unittest.TestCase):
    def test_only_one_lock_with_the_same_name_can_be_held(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            name = f"PokemonCardCollection-Test-{uuid.uuid4().hex}"
            metadata = Path(directory) / "server.lock"
            first = RuntimeLock(name, metadata)
            second = RuntimeLock(name, metadata)

            self.assertTrue(first.acquire())
            self.assertFalse(second.acquire())
            self.assertIn("pid=", metadata.read_text(encoding="ascii"))

            first.release()
            self.assertTrue(second.acquire())
            second.release()


if __name__ == "__main__":
    unittest.main()
