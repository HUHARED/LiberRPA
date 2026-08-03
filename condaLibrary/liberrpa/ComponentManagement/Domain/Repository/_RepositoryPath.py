# FileName: _RepositoryPath.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Common._BasicConfig import get_basic_config_dict
from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError

from pathlib import Path


def get_repository_path() -> Path:
    try:
        dictBasicConfig = get_basic_config_dict(toolName="Editor")

        pathRepository = Path(dictBasicConfig["componentRepositoryPath"]).expanduser()

        if not pathRepository.is_absolute():
            raise ComponentManagementError(
                code="repository_unavailable",
                message=("componentRepositoryPath must be an absolute path."),
            )

        pathRepository = pathRepository.resolve()
    except ComponentManagementError:
        raise

    except (OSError, RuntimeError, ValueError) as e:
        raise ComponentManagementError(
            code="repository_unavailable",
            message="Failed to read the Component Repository path from basic.jsonc.",
        ) from e

    if not pathRepository.is_dir():
        raise ComponentManagementError(
            code="repository_unavailable",
            message=f"Component Repository folder was not found: {pathRepository}",
        )

    return pathRepository
