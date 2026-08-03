# FileName: _VersionEntry.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Types._Manifest import Info_ProjectManifest_Component
from liberrpa.ComponentManagement.Types._Repository import DictRepository_ComponentVersion


def build_repository_version_entry(
    manifestObj: Info_ProjectManifest_Component,
    wheelFile: str,
    sha256: str,
) -> DictRepository_ComponentVersion:
    return {
        "version": manifestObj.version,
        "displayName": manifestObj.displayName,
        "description": manifestObj.description,
        "wheelFile": wheelFile,
        "sha256": sha256,
        "requiresLiberrpa": manifestObj.requiresLiberrpa,
        "componentDependencies": dict(sorted(manifestObj.componentDependencies.items())),
    }
