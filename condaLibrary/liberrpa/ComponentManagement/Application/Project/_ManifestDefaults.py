# FileName: _ManifestDefaults.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Common._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Common._Version import (
    get_default_requires_liberrpa,
    get_installed_liberrpa_version,
)


def get_project_manifest_defaults() -> tuple[str, str]:
    try:
        versionObj = get_installed_liberrpa_version()
    except ValueError as e:
        raise ComponentManagementError(
            code="liberrpa_version_unavailable",
            message="The installed liberrpa version could not be determined.",
            details={"reason": str(e)},
        ) from e

    return str(versionObj), get_default_requires_liberrpa(versionObj)
