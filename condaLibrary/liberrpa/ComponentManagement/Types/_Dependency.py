# FileName: _Dependency.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Types._Warning import DictComponentManagementWarning
from liberrpa.ComponentManagement.Types._Manifest import Str_ProjectTypeValue, Info_ProjectManifest
from liberrpa.ComponentManagement.Types._Components import DictComponentsLock_File, Info_ProjectComponentsFolder


from pathlib import Path
from dataclasses import dataclass
from typing import Literal, NotRequired, TypedDict


@dataclass(frozen=True)
class Info_ProjectDependency_Operation_Add:
    componentId: str
    requirement: str


@dataclass(frozen=True)
class Info_ProjectDependency_Operation_Update:
    componentIds: tuple[str, ...]


@dataclass(frozen=True)
class Info_ProjectDependency_Operation_ChangeRequirement:
    componentId: str
    requirement: str


@dataclass(frozen=True)
class Info_ProjectDependency_Operation_Remove:
    componentId: str


type Info_ProjectDependency_Operation = (
    Info_ProjectDependency_Operation_Add
    | Info_ProjectDependency_Operation_Update
    | Info_ProjectDependency_Operation_ChangeRequirement
    | Info_ProjectDependency_Operation_Remove
)


type Str_ProjectDependency_DirectChange = Literal["added", "removed", "requirementChanged"]


class DictProjectDependency_DirectChange(TypedDict):
    componentId: str
    change: Str_ProjectDependency_DirectChange
    previousRequirement: NotRequired[str]
    targetRequirement: NotRequired[str]


type Str_ProjectDependency_ResolvedChange = Literal["added", "removed", "upgraded", "downgraded"]


class DictProjectDependency_ResolvedChange(TypedDict):
    componentId: str
    packageName: str
    displayName: str
    change: Str_ProjectDependency_ResolvedChange
    previousVersion: NotRequired[str]
    targetVersion: NotRequired[str]


@dataclass(frozen=True)
class Info_ProjectDependency_Plan:
    operation: Info_ProjectDependency_Operation
    sourceManifest: Info_ProjectManifest
    sourceComponentsLock: DictComponentsLock_File | None
    targetManifest: Info_ProjectManifest
    targetComponentsLock: DictComponentsLock_File | None
    directDependencyChanges: list[DictProjectDependency_DirectChange]
    resolvedComponentChanges: list[DictProjectDependency_ResolvedChange]
    planSha256: str


@dataclass(frozen=True)
class Info_ProjectDependency_ApplyResult:
    plan: Info_ProjectDependency_Plan
    componentsFolderInfo: Info_ProjectComponentsFolder | None
    warnings: list[DictComponentManagementWarning]


@dataclass(frozen=True)
class Info_ProjectDependency_RepairResult:
    componentsFolderInfo: Info_ProjectComponentsFolder
    warnings: list[DictComponentManagementWarning]


type Str_ProjectDependency_LockState = Literal["notRequired", "missing", "invalid", "stale", "valid"]
type Str_ProjectDependency_ComponentsState = Literal["notRequired", "unverified", "missing", "damaged", "valid"]
type Str_ProjectDependency_EnvironmentState = Literal["unknown", "compatible", "incompatible"]
type Str_ProjectDependency_RepairState = Literal[
    "notApplicable",
    "available",
    "repositoryUnavailable",
    "wheelMissing",
    "wheelHashMismatch",
]


@dataclass(frozen=True)
class Info_ProjectDependency_State:
    projectPath: Path
    projectType: Str_ProjectTypeValue
    manifest: Info_ProjectManifest
    componentsLock: DictComponentsLock_File | None
    lockState: Str_ProjectDependency_LockState
    componentsState: Str_ProjectDependency_ComponentsState
    environmentState: Str_ProjectDependency_EnvironmentState
    repairState: Str_ProjectDependency_RepairState
    details: dict[str, object]
