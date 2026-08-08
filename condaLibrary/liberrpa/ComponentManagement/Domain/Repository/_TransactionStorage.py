# FileName: _TransactionStorage.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Types._Warning import DictComponentManagementWarning

from pathlib import Path
import os
import shutil


_STR_STAGING_FOLDER_NAME = ".staging"


def get_repository_staging_folder_path(repositoryPath: Path) -> Path:
    return repositoryPath / _STR_STAGING_FOLDER_NAME


def copy_wheel_to_staging(sourcePath: Path, targetPath: Path) -> None:
    try:
        with (
            sourcePath.open("rb") as sourceFileObj,
            targetPath.open("xb") as targetFileObj,
        ):
            shutil.copyfileobj(sourceFileObj, targetFileObj, length=1024 * 1024)
            targetFileObj.flush()
            os.fsync(targetFileObj.fileno())
    except OSError as e:
        raise ComponentManagementError(
            code="io_error",
            message=(
                f"Failed to copy the Component Wheel into Repository staging: {targetPath}"
            ),
        ) from e


def remove_repository_transaction_folder(
    transactionFolderPath: Path,
) -> DictComponentManagementWarning | None:
    try:
        shutil.rmtree(transactionFolderPath)
    except OSError as e:
        return {
            "code": "repository_cleanup_pending",
            "message": (
                "Repository transaction recovery completed, but temporary files could not be removed: "
                f"{transactionFolderPath}"
            ),
            "details": {"reason": str(e)},
        }

    return None
