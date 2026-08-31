"""Single-instance runtime guard for the local collection server."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
from typing import BinaryIO


def _windows_kernel32():
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    return kernel32


class RuntimeLock:
    """Hold one named server instance across checkouts and terminal windows."""

    def __init__(self, name: str, metadata_path: Path) -> None:
        self.name = "".join(character if character.isalnum() else "-" for character in name)
        self.metadata_path = Path(metadata_path)
        self._mutex: int | None = None
        self._file: BinaryIO | None = None

    def acquire(self) -> bool:
        if self._mutex is not None or self._file is not None:
            return True
        if os.name == "nt":
            kernel32 = _windows_kernel32()
            handle = kernel32.CreateMutexW(None, False, f"Local\\{self.name}")
            if not handle:
                raise OSError(ctypes.get_last_error(), "Could not create the server lock.")
            if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
                kernel32.CloseHandle(handle)
                return False
            self._mutex = int(handle)
        else:
            import fcntl

            self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
            handle = self.metadata_path.open("a+b")
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                handle.close()
                return False
            self._file = handle
        self._write_metadata()
        return True

    def _write_metadata(self) -> None:
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.metadata_path.write_text(f"pid={os.getpid()}\n", encoding="ascii")
        except OSError:
            pass

    def release(self) -> None:
        if self._mutex is not None:
            self.metadata_path.unlink(missing_ok=True)
            kernel32 = _windows_kernel32()
            kernel32.CloseHandle(self._mutex)
            self._mutex = None
        if self._file is not None:
            import fcntl

            fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
            self._file.close()
            self._file = None

    def __enter__(self) -> "RuntimeLock":
        if not self.acquire():
            raise RuntimeError("The runtime lock is already held.")
        return self

    def __exit__(self, *_exc: object) -> None:
        self.release()
