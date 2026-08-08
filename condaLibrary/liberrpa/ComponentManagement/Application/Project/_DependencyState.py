# FileName: _DependencyState.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._Project import resolve_project_path
from liberrpa.ComponentManagement.Types._Warning import DictComponentManagementWarning
from liberrpa.ComponentManagement.Types._Dependency import Info_ProjectDependency_State
from liberrpa.ComponentManagement.Application.Project._TransactionRecovery import (
    recover_project_transactions,
)
from liberrpa.ComponentManagement.Domain.Dependency._State import (
    get_project_dependency_state,
)

from pathlib import Path


def get_current_project_dependency_state(
    projectPath: str | Path,
) -> tuple[Info_ProjectDependency_State, list[DictComponentManagementWarning]]:
    pathProject = resolve_project_path(projectPath)

    listWarning = recover_project_transactions(pathProject)

    stateObj = get_project_dependency_state(pathProject)

    return stateObj, listWarning
