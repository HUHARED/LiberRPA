# FileName: local_locks.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import errno
import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path


class LocalLockUnavailableError(Exception):
    """Another process on this host owns the requested file lock."""


@contextmanager
def hold_local_lock(path: Path, *, wait: bool = False) -> Generator[None]:
    """Keep protection until the actual process releases its handle, independently of its database connection."""
    # NOTE: Never replace or delete a lock file while Console processes can use it.
    with path.open("a+b") as handle:
        try:
            if os.name == "nt":
                import msvcrt

                if handle.seek(0, os.SEEK_END) == 0:
                    handle.write(b"0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(
                    handle.fileno(), msvcrt.LK_LOCK if wait else msvcrt.LK_NBLCK, 1
                )
            else:
                import fcntl

                fcntl.flock(handle, fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
        except OSError as e:
            if e.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                raise LocalLockUnavailableError(
                    "The requested operation is already in progress."
                ) from None
            raise
        yield
