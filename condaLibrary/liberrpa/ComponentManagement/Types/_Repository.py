# FileName: _Repository.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Types._Warning import DictComponentManagementWarning

from pathlib import Path
from dataclasses import dataclass
from typing import Literal, TypedDict


type Str_Repository_Error_Code = Literal[
    "repository_recovery_failed", "repository_rebuild_failed"
]


class DictRepository_ComponentVersionEntry(TypedDict):
    version: str
    displayName: str
    description: str
    requiresLiberrpa: str
    componentDependencies: dict[str, str]

    wheelFileName: str
    sha256: str


class DictRepository_Component(TypedDict):
    packageName: str
    versions: list[DictRepository_ComponentVersionEntry]


class DictRepository_Index(TypedDict):
    schemaVersion: Literal[1]
    components: dict[str, DictRepository_Component]


class DictRepository_Transaction_Publish(TypedDict):
    schemaVersion: Literal[1]
    operation: Literal["publishComponent"]
    state: Literal["prepared", "wheelCommitted"]

    componentId: str
    packageName: str

    versionEntry: DictRepository_ComponentVersionEntry

    targetRelativePath: str


class DictRepository_Transaction_ImportArtifact(TypedDict):
    artifactRelativePath: str

    componentId: str
    packageName: str

    versionEntry: DictRepository_ComponentVersionEntry

    targetRelativePath: str


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
    sourceWheelFilePath: Path

    componentId: str
    packageName: str
    version: str

    wheelFileName: str
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
