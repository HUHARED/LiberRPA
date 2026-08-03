# FileName: _Manifest.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from dataclasses import dataclass
from typing import Literal


type Str_ProjectType = Literal["flow", "component"]


@dataclass(frozen=True)
class Info_ProjectManifest_Flow:
    """Validated and normalized flow.json data used inside Component Management."""

    name: str

    version: str
    description: str
    requiresLiberrpa: str
    componentDependencies: dict[str, str]


@dataclass(frozen=True)
class Info_ProjectManifest_Component:
    """Validated and normalized component.json data used inside Component Management."""

    id: str
    packageName: str
    displayName: str

    version: str
    description: str
    requiresLiberrpa: str
    componentDependencies: dict[str, str]


type Info_ProjectManifest = Info_ProjectManifest_Flow | Info_ProjectManifest_Component
