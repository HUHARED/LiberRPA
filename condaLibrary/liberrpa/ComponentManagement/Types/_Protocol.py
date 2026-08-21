# FileName: _Protocol.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Types._Warning import DictComponentManagementWarning
from liberrpa.ComponentManagement.Types._Manifest import Str_ProjectType
from liberrpa.ComponentManagement.Types._Components import DictComponentsLock_File
from liberrpa.ComponentManagement.Types._Repository import (
    DictRepository_ComponentVersionEntry,
)
from liberrpa.ComponentManagement.Types._Dependency import (
    DictProjectDependency_DirectChange,
    DictProjectDependency_ResolvedChange,
    Str_ProjectDependency_LockState,
    Str_ProjectDependency_ComponentsState,
    Str_ProjectDependency_EnvironmentState,
    Str_ProjectDependency_RepairState,
)


from typing import Literal, TypedDict


class DictProtocolDependencyOperation_Add(TypedDict):
    operation: Literal["addComponentDependency"]
    componentId: str
    requirement: str


class DictProtocolDependencyOperation_Update(TypedDict):
    operation: Literal["updateComponents"]
    componentIds: list[str]


class DictProtocolDependencyOperation_Resolve(TypedDict):
    operation: Literal["resolveProjectDependencies"]


class DictProtocolDependencyOperation_ChangeRequirement(TypedDict):
    operation: Literal["changeComponentRequirement"]
    componentId: str
    requirement: str


class DictProtocolDependencyOperation_Remove(TypedDict):
    operation: Literal["removeComponentDependency"]
    componentId: str


type DictProtocolDependencyOperation = (
    DictProtocolDependencyOperation_Add
    | DictProtocolDependencyOperation_Update
    | DictProtocolDependencyOperation_Resolve
    | DictProtocolDependencyOperation_ChangeRequirement
    | DictProtocolDependencyOperation_Remove
)


class DictProtocolRequest_PublishComponent(TypedDict):
    schemaVersion: Literal[1]
    operation: Literal["publishComponent"]

    projectPath: str


class DictProtocolRequest_ImportComponentWheels(TypedDict):
    schemaVersion: Literal[1]
    operation: Literal["importComponentWheels"]

    wheelFilePaths: list[str]


class DictProtocolRequest_RebuildRepositoryIndex(TypedDict):
    schemaVersion: Literal[1]
    operation: Literal["rebuildRepositoryIndex"]


class DictProtocolRequest_GetComponentRepositoryCatalog(TypedDict):
    schemaVersion: Literal[1]
    operation: Literal["getComponentRepositoryCatalog"]


class DictProtocolRequest_GetProjectManifestDefaults(TypedDict):
    schemaVersion: Literal[1]
    operation: Literal["getProjectManifestDefaults"]


class DictProtocolRequest_GetProjectDependencyState(TypedDict):
    schemaVersion: Literal[1]
    operation: Literal["getProjectDependencyState"]

    projectPath: str


class DictProtocolRequest_ValidatePackagedFlowProject(TypedDict):
    schemaVersion: Literal[1]
    operation: Literal["validatePackagedFlowProject"]

    projectPath: str


class DictProtocolRequest_BuildProjectDependencyPlan(TypedDict):
    schemaVersion: Literal[1]
    operation: Literal["buildProjectDependencyPlan"]

    projectPath: str
    dependencyOperation: DictProtocolDependencyOperation


class DictProtocolRequest_ApplyProjectDependencyPlan(TypedDict):
    schemaVersion: Literal[1]
    operation: Literal["applyProjectDependencyPlan"]

    projectPath: str
    dependencyOperation: DictProtocolDependencyOperation
    confirmedPlanSha256: str


class DictProtocolRequest_RepairProjectComponents(TypedDict):
    schemaVersion: Literal[1]
    operation: Literal["repairProjectComponents"]

    projectPath: str


type DictProtocolRequest = (
    DictProtocolRequest_PublishComponent
    | DictProtocolRequest_ImportComponentWheels
    | DictProtocolRequest_RebuildRepositoryIndex
    | DictProtocolRequest_GetComponentRepositoryCatalog
    | DictProtocolRequest_GetProjectManifestDefaults
    | DictProtocolRequest_GetProjectDependencyState
    | DictProtocolRequest_ValidatePackagedFlowProject
    | DictProtocolRequest_BuildProjectDependencyPlan
    | DictProtocolRequest_ApplyProjectDependencyPlan
    | DictProtocolRequest_RepairProjectComponents
)


class _DictProtocolResult_PublishBase(TypedDict):
    componentId: str
    packageName: str

    astSnippetsFile: str
    snippetsJsoncFile: str
    generatedCount: int
    skippedCount: int
    warningCount: int


class _DictProtocolResult_Publish_PreparationCreated(_DictProtocolResult_PublishBase):
    status: Literal["preparationCreated"]


class _DictProtocolResult_Publish_Published(_DictProtocolResult_PublishBase):
    status: Literal["published", "alreadyPublished"]

    version: str

    excludedCount: int
    handWrittenCount: int
    finalCount: int

    wheelFileName: str
    sha256: str


type DictProtocolResult_Publish = (
    _DictProtocolResult_Publish_PreparationCreated | _DictProtocolResult_Publish_Published
)


class DictProtocolResult_ComponentWheelsImported_Component(TypedDict):
    # It has the same values with Info_Repository_Import_ComponentResult.
    sourceWheelFilePath: str

    componentId: str
    packageName: str
    version: str

    wheelFileName: str
    sha256: str

    status: Literal["imported", "alreadyImported"]


class DictProtocolResult_ComponentWheelsImported(TypedDict):
    status: Literal["componentWheelsImported"]
    importedCount: int
    alreadyImportedCount: int
    components: list[DictProtocolResult_ComponentWheelsImported_Component]


class DictProtocolResult_RepositoryIndexRebuilt(TypedDict):
    status: Literal["repositoryIndexRebuilt"]
    componentCount: int
    versionCount: int


class DictProtocolResult_RepositoryCatalog_Component(TypedDict):
    componentId: str
    packageName: str
    versions: list[DictRepository_ComponentVersionEntry]


class DictProtocolResult_RepositoryCatalog(TypedDict):
    status: Literal["componentRepositoryCatalog"]
    repositoryPath: str
    componentCount: int
    versionCount: int
    components: list[DictProtocolResult_RepositoryCatalog_Component]


class DictProtocolResult_ProjectManifestDefaults(TypedDict):
    status: Literal["projectManifestDefaults"]
    installedLiberrpaVersion: str
    requiresLiberrpa: str


class DictProtocolResult_ComponentsFolder(TypedDict):
    componentsFolderPath: str
    componentCount: int
    fileCount: int


class DictProtocolResult_ProjectDependencyState(TypedDict):
    status: Literal["projectDependencyState"]
    projectPath: str
    projectType: Str_ProjectType
    manifest: dict[str, object]
    componentsLock: DictComponentsLock_File | None
    lockState: Str_ProjectDependency_LockState
    componentsState: Str_ProjectDependency_ComponentsState
    environmentState: Str_ProjectDependency_EnvironmentState
    repairState: Str_ProjectDependency_RepairState
    details: dict[str, object]


class DictProtocolResult_PackagedFlowProjectValidated(TypedDict):
    status: Literal["packagedFlowProjectValidated"]


class DictProtocolResult_ProjectDependencyPlan(TypedDict):
    status: Literal["projectDependencyPlanCreated"]
    planSha256: str
    sourceManifest: dict[str, object]
    sourceComponentsLock: DictComponentsLock_File | None
    targetManifest: dict[str, object]
    targetComponentsLock: DictComponentsLock_File | None
    directDependencyChanges: list[DictProjectDependency_DirectChange]
    resolvedComponentChanges: list[DictProjectDependency_ResolvedChange]


class DictProtocolResult_ProjectDependencyPlanApplied(TypedDict):
    status: Literal["projectDependencyPlanApplied"]
    planSha256: str
    targetManifest: dict[str, object]
    targetComponentsLock: DictComponentsLock_File | None
    directDependencyChanges: list[DictProjectDependency_DirectChange]
    resolvedComponentChanges: list[DictProjectDependency_ResolvedChange]
    componentsFolder: DictProtocolResult_ComponentsFolder | None


class DictProtocolResult_ProjectComponentsRepaired(TypedDict):
    status: Literal["projectComponentsRepaired"]
    componentsFolder: DictProtocolResult_ComponentsFolder


type DictProtocolResult = (
    DictProtocolResult_Publish
    | DictProtocolResult_ComponentWheelsImported
    | DictProtocolResult_RepositoryIndexRebuilt
    | DictProtocolResult_RepositoryCatalog
    | DictProtocolResult_ProjectManifestDefaults
    | DictProtocolResult_ProjectDependencyState
    | DictProtocolResult_PackagedFlowProjectValidated
    | DictProtocolResult_ProjectDependencyPlan
    | DictProtocolResult_ProjectDependencyPlanApplied
    | DictProtocolResult_ProjectComponentsRepaired
)


class DictProtocolError(TypedDict):
    code: str
    message: str
    details: dict[str, object]


class DictProtocolSuccess_PublishComponent(TypedDict):
    schemaVersion: Literal[1]
    ok: Literal[True]
    result: DictProtocolResult_Publish
    warnings: list[DictComponentManagementWarning]


class DictProtocolSuccess_ComponentWheelsImported(TypedDict):
    schemaVersion: Literal[1]
    ok: Literal[True]
    result: DictProtocolResult_ComponentWheelsImported
    warnings: list[DictComponentManagementWarning]


class DictProtocolSuccess_RepositoryIndexRebuilt(TypedDict):
    schemaVersion: Literal[1]
    ok: Literal[True]
    result: DictProtocolResult_RepositoryIndexRebuilt
    warnings: list[DictComponentManagementWarning]


class DictProtocolSuccess_RepositoryCatalog(TypedDict):
    schemaVersion: Literal[1]
    ok: Literal[True]
    result: DictProtocolResult_RepositoryCatalog
    warnings: list[DictComponentManagementWarning]


class DictProtocolSuccess_ProjectManifestDefaults(TypedDict):
    schemaVersion: Literal[1]
    ok: Literal[True]
    result: DictProtocolResult_ProjectManifestDefaults
    warnings: list[DictComponentManagementWarning]


class DictProtocolSuccess_ProjectDependencyState(TypedDict):
    schemaVersion: Literal[1]
    ok: Literal[True]
    result: DictProtocolResult_ProjectDependencyState
    warnings: list[DictComponentManagementWarning]


class DictProtocolSuccess_PackagedFlowProjectValidated(TypedDict):
    schemaVersion: Literal[1]
    ok: Literal[True]
    result: DictProtocolResult_PackagedFlowProjectValidated
    warnings: list[DictComponentManagementWarning]


class DictProtocolSuccess_ProjectDependencyPlan(TypedDict):
    schemaVersion: Literal[1]
    ok: Literal[True]
    result: DictProtocolResult_ProjectDependencyPlan
    warnings: list[DictComponentManagementWarning]


class DictProtocolSuccess_ProjectDependencyPlanApplied(TypedDict):
    schemaVersion: Literal[1]
    ok: Literal[True]
    result: DictProtocolResult_ProjectDependencyPlanApplied
    warnings: list[DictComponentManagementWarning]


class DictProtocolSuccess_ProjectComponentsRepaired(TypedDict):
    schemaVersion: Literal[1]
    ok: Literal[True]
    result: DictProtocolResult_ProjectComponentsRepaired
    warnings: list[DictComponentManagementWarning]


type DictProtocolSuccess = (
    DictProtocolSuccess_PublishComponent
    | DictProtocolSuccess_ComponentWheelsImported
    | DictProtocolSuccess_RepositoryIndexRebuilt
    | DictProtocolSuccess_RepositoryCatalog
    | DictProtocolSuccess_ProjectManifestDefaults
    | DictProtocolSuccess_ProjectDependencyState
    | DictProtocolSuccess_PackagedFlowProjectValidated
    | DictProtocolSuccess_ProjectDependencyPlan
    | DictProtocolSuccess_ProjectDependencyPlanApplied
    | DictProtocolSuccess_ProjectComponentsRepaired
)


class DictProtocolResponse_Error(TypedDict):
    schemaVersion: Literal[1]
    ok: Literal[False]
    error: DictProtocolError


type DictProtocolResponse = DictProtocolSuccess | DictProtocolResponse_Error
