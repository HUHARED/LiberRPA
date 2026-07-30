# FileName: _Repository.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Types._Warning import DictComponentManagementWarning

from pathlib import Path
from dataclasses import dataclass
from typing import Literal, TypedDict


class DictRepository_ComponentVersion(TypedDict):
    version: str
    displayName: str
    description: str
    manifestSchemaVersion: Literal[1]
    wheelFile: str
    sha256: str
    requiresLiberrpa: str
    componentDependencies: dict[str, str]


class DictRepository_Component(TypedDict):
    packageName: str
    versions: list[DictRepository_ComponentVersion]


class DictRepository_Index(TypedDict):
    schemaVersion: Literal[1]
    components: dict[str, DictRepository_Component]


class DictRepository_Transaction_Publish(TypedDict):
    schemaVersion: Literal[1]
    operation: Literal["publishComponent"]
    state: Literal["prepared", "wheelCommitted"]
    componentId: str
    packageName: str
    version: str
    wheelFile: str
    sha256: str
    targetRelativePath: str
    versionEntry: DictRepository_ComponentVersion


class DictRepository_Transaction_ImportArtifact(TypedDict):
    artifactRelativePath: str
    componentId: str
    packageName: str
    version: str
    wheelFile: str
    sha256: str
    targetRelativePath: str
    versionEntry: DictRepository_ComponentVersion


class DictRepository_Transaction_Import(TypedDict):
    schemaVersion: Literal[1]
    operation: Literal["importComponentWheels"]
    state: Literal["prepared", "wheelsCommitted"]
    artifacts: list[DictRepository_Transaction_ImportArtifact]


@dataclass(frozen=True)
class Info_Repository_PublishResult:
    status: Literal["published", "alreadyPublished"]
    warnings: list[DictComponentManagementWarning]


@dataclass(frozen=True)
class Info_Repository_Import_ComponentResult:
    sourcePath: Path
    componentId: str
    packageName: str
    version: str
    wheelFile: str
    sha256: str
    status: Literal["imported", "alreadyImported"]


@dataclass(frozen=True)
class Info_Repository_ImportResult:
    components: list[Info_Repository_Import_ComponentResult]
    warnings: list[DictComponentManagementWarning]


@dataclass(frozen=True)
class Info_Repository_RebuildResult:
    componentCount: int
    versionCount: int
    warnings: list[DictComponentManagementWarning]
