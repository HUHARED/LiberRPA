# FileName: _Wheel.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from liberrpa.ComponentManagement.Types._Manifest import Info_ProjectManifest_Component
from liberrpa.ComponentManagement.Types._Snippet import DictSnippet_CatalogFile


from pathlib import Path
from dataclasses import dataclass


@dataclass(frozen=True)
class Info_ComponentWheel_BuildResult:
    wheelPath: Path
    wheelFile: str
    sha256: str


@dataclass(frozen=True)
class Info_ComponentWheel:
    manifest: Info_ProjectManifest_Component
    snippetCatalog: DictSnippet_CatalogFile
    wheelFile: str
    sha256: str
