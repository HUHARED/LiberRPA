# FileName: _RepositoryLock.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Domain.Lock._Lock import create_lock, release_lock

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path


_STR_LOCK_FILE_NAME = ".repository.lock"


@contextmanager
def repository_lock(repositoryPath: Path, operation: str) -> Generator[None]:
    pathLock = repositoryPath / _STR_LOCK_FILE_NAME
    strOwnerId = create_lock(
        lockPath=pathLock,
        operation=operation,
        lockType="repository",
    )

    try:
        yield
    finally:
        release_lock(lockPath=pathLock, ownerId=strOwnerId)
