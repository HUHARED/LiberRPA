# FileName: _WheelName.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from packaging.tags import Tag
from packaging.utils import canonicalize_name


STR_COMPONENT_WHEEL_TAG = "py313-none-any"  # Without any binary file related to system platforms or CPU architectures.
TAG_COMPONENT_WHEEL = Tag("py313", "none", "any")


def get_component_wheel_names(packageName: str, version: str) -> tuple[str, str]:
    strDistributionName = canonicalize_name(packageName).replace("-", "_")
    strDistInfoFolder = f"{strDistributionName}-{version}.dist-info"
    strWheelFile = f"{strDistributionName}-{version}-{STR_COMPONENT_WHEEL_TAG}.whl"
    return strDistInfoFolder, strWheelFile
