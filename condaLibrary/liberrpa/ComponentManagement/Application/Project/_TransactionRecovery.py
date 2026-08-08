# FileName: _TransactionRecovery.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Types._Warning import DictComponentManagementWarning
from liberrpa.ComponentManagement.Domain.Lock._ProjectLock import project_lock
from liberrpa.ComponentManagement.Domain.Project._TransactionLifecycle import (
    recover_project_transactions_locked,
)

from pathlib import Path


def recover_project_transactions(
    projectPath: Path,
) -> list[DictComponentManagementWarning]:
    """Recover one interrupted Project dependency transaction under the Project lock."""

    with project_lock(projectPath, "recoverProjectDependencyTransaction"):
        return recover_project_transactions_locked(projectPath)
