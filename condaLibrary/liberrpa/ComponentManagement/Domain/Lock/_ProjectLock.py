# FileName: _ProjectLock.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Domain.Lock._Lock import create_lock, release_lock

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path


_STR_LOCK_FILE_NAME = ".liberrpa-project-manager.lock"


@contextmanager
def project_lock(projectPath: Path, operation: str) -> Generator[None]:
    pathProjectLockFile = projectPath / _STR_LOCK_FILE_NAME
    strOwnerId = create_lock(
        lockFilePath=pathProjectLockFile,
        operation=operation,
        lockType="project",
    )

    try:
        yield
    finally:
        release_lock(lockFilePath=pathProjectLockFile, ownerId=strOwnerId)
