# FileName: _Components.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from typing import Literal, TypedDict
from pathlib import Path
from dataclasses import dataclass


class DictComponentsLock_Root_FlowProject(TypedDict):
    manifestFile: Literal["flow.json"]
    requiresLiberrpa: str
    componentDependencies: dict[str, str]


class DictComponentsLock_Root_ComponentProject(TypedDict):
    manifestFile: Literal["component.json"]
    componentId: str
    packageName: str
    requiresLiberrpa: str
    componentDependencies: dict[str, str]


type DictComponentsLock_Root = DictComponentsLock_Root_FlowProject | DictComponentsLock_Root_ComponentProject


class DictComponentsLock_Component(TypedDict):
    packageName: str
    displayName: str
    version: str
    wheelFileName: str
    sha256: str
    requiresLiberrpa: str
    componentDependencies: dict[str, str]


class DictComponentsLock_File(TypedDict):
    """components.lock.json in a Flow or Component Project."""

    schemaVersion: Literal[1]
    root: DictComponentsLock_Root
    components: dict[str, DictComponentsLock_Component]


@dataclass(frozen=True)
class Info_ProjectComponentsFolder:
    componentsPath: Path
    componentCount: int
    fileCount: int
