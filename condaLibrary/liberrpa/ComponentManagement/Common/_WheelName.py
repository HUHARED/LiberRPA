# FileName: _WheelName.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._Validation import (
    get_windows_file_or_folder_name_error,
)

from packaging.tags import Tag
from packaging.utils import canonicalize_name


STR_COMPONENT_WHEEL_TAG = "py313-none-any"  # Without any binary file related to system platforms or CPU architectures.
TAG_COMPONENT_WHEEL = Tag("py313", "none", "any")


def get_component_wheel_names(packageName: str, version: str) -> tuple[str, str]:
    strDistributionName = canonicalize_name(packageName).replace("-", "_")
    strDistInfoFolder = f"{strDistributionName}-{version}.dist-info"
    strWheelFileName = f"{strDistributionName}-{version}-{STR_COMPONENT_WHEEL_TAG}.whl"

    for strEntryName, strDescription in (
        (strWheelFileName, "Component Wheel filename"),
        (strDistInfoFolder, "Component dist-info folder name"),
    ):
        strEntryNameError = get_windows_file_or_folder_name_error(
            strEntryName,
            strDescription,
        )
        if strEntryNameError is not None:
            raise ValueError(strEntryNameError)

    return strDistInfoFolder, strWheelFileName
