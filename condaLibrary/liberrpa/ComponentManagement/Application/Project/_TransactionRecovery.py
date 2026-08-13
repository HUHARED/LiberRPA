# FileName: _TransactionRecovery.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._DiagnosticLog import DiagnosticLog
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

    DiagnosticLog.debug(f"Checking interrupted Project transactions: {projectPath}")
    with project_lock(projectPath, "recoverProjectDependencyTransaction"):
        listWarning = recover_project_transactions_locked(projectPath)

    if listWarning:
        DiagnosticLog.warning(
            message=f"Project transaction recovery completed with {len(listWarning)} warning(s)."
        )
    else:
        DiagnosticLog.debug("Project transaction recovery check completed.")

    return listWarning
