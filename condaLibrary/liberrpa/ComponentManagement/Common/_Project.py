# FileName: _Project.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError

from pathlib import Path


def resolve_project_path(projectPath: str | Path) -> Path:
    """Resolve and validate a LiberRPA Project folder path."""
    try:
        pathProject = Path(projectPath).expanduser().resolve()
    except (OSError, RuntimeError, ValueError) as e:
        raise ComponentManagementError(
            code="project_path_invalid",
            message=f"Failed to resolve the Project path: {projectPath}",
        ) from e

    if not pathProject.is_dir():
        raise ComponentManagementError(
            code="project_path_invalid",
            message=f"Project folder was not found: {pathProject}",
        )

    return pathProject
