# FileName: _RepositorySnapshot.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Types._Warning import DictComponentManagementWarning
from liberrpa.ComponentManagement.Types._Repository import DictRepository_Index
from liberrpa.ComponentManagement.Domain.Lock._RepositoryLock import repository_lock
from liberrpa.ComponentManagement.Domain.Repository._Index import load_repository_index
from liberrpa.ComponentManagement.Domain.Repository._RepositoryPath import (
    get_repository_path,
)
from liberrpa.ComponentManagement.Domain.Repository._Transaction import (
    recover_repository_transactions,
)

from pathlib import Path


def _load_repository_index_snapshot(
    operation: str,
) -> tuple[
    Path,
    DictRepository_Index,
    list[DictComponentManagementWarning],
]:
    pathRepository = get_repository_path()

    with repository_lock(pathRepository, operation):
        listWarning = recover_repository_transactions(pathRepository)

        dictIndex = load_repository_index(pathRepository, checkWheelFilePaths=True)

    return pathRepository, dictIndex, listWarning


def load_repository_resolution_snapshot() -> tuple[
    DictRepository_Index,
    list[DictComponentManagementWarning],
]:
    """Read a consistent Repository index snapshot for dependency resolution."""
    _, dictIndex, listWarning = _load_repository_index_snapshot(
        "resolveProjectDependencies"
    )

    return dictIndex, listWarning


def load_repository_catalog_snapshot() -> tuple[
    Path,
    DictRepository_Index,
    list[DictComponentManagementWarning],
]:
    """Read a consistent Repository index snapshot for display and selection."""
    return _load_repository_index_snapshot("getComponentRepositoryCatalog")
