# FileName: _TypedValue.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from pathlib import Path
from dataclasses import dataclass
from typing import Literal, NotRequired, TypedDict


class DictOperationWarning(TypedDict):
    code: str
    message: str
    details: NotRequired[dict[str, object]]


##### Manifest #####

type ProjectType = Literal["flow", "component"]


@dataclass(frozen=True)
class FlowManifest:
    """flow.json in a Flow Project"""

    schemaVersion: Literal[1]
    name: str
    version: str
    description: str
    requiresLiberrpa: str
    componentDependencies: dict[str, str]


@dataclass(frozen=True)
class ComponentManifest:
    """component.json in a Component Project"""

    schemaVersion: Literal[1]
    id: str
    packageName: str
    displayName: str
    version: str
    description: str
    requiresLiberrpa: str
    componentDependencies: dict[str, str]


type ProjectManifest = FlowManifest | ComponentManifest


##### Snippet attributes #####


type SnippetInsertionMode = Literal["line", "cursor"]
type DictSnippetImports = dict[str, list[str]]  # "SourceName": ["ModuleName1", "ModuleName2", ...]


class DictNormalizedSnippet(TypedDict):
    category: str
    label: str

    prefix: str
    body: list[str]
    description: str

    imports: DictSnippetImports
    insertionMode: SnippetInsertionMode


class DictSnippetDiagnostic(TypedDict):
    code: str
    file: str
    line: int
    functionName: NotRequired[str]
    message: str


class DictAstSnippetsFile(TypedDict):
    """_Snippets/ast.snippets.json"""

    schemaVersion: Literal[1]
    componentId: str
    packageName: str
    snippets: dict[str, DictNormalizedSnippet]
    skipped: list[DictSnippetDiagnostic]
    warnings: list[DictSnippetDiagnostic]


class DictImportSourceConfig(TypedDict):
    order: list[str]
    aliasMode: NotRequired[Literal["source_module"]]


class DictSnippetCatalogFile(TypedDict):
    """snippets_catalog.json in a Component Wheel."""

    schemaVersion: Literal[1]
    categoryOrder: list[str]
    importSources: dict[str, DictImportSourceConfig]
    snippets: dict[str, DictNormalizedSnippet]


class DictAstSnippetOverride(TypedDict):
    label: NotRequired[str]
    body: NotRequired[list[str]]
    description: NotRequired[str]
    insertionMode: NotRequired[SnippetInsertionMode]
    imports: NotRequired[DictSnippetImports]


class DictSnippetConfigWarning(TypedDict):
    code: str
    message: str
    snippetKey: str


type DictComponentManagementWarning = DictSnippetDiagnostic | DictSnippetConfigWarning | DictOperationWarning

##### Wheel #####


@dataclass(frozen=True)
class WheelBuildResult:
    wheelPath: Path
    wheelFile: str
    sha256: str


@dataclass(frozen=True)
class ComponentWheelInfo:
    manifest: ComponentManifest
    snippetCatalog: DictSnippetCatalogFile
    wheelFile: str
    sha256: str


##### Repository #####


class DictRepositoryComponentVersion(TypedDict):
    version: str
    displayName: str
    description: str
    manifestSchemaVersion: Literal[1]
    wheelFile: str
    sha256: str
    requiresLiberrpa: str
    componentDependencies: dict[str, str]


class DictRepositoryComponent(TypedDict):
    packageName: str
    versions: list[DictRepositoryComponentVersion]


class DictRepositoryIndex(TypedDict):
    schemaVersion: Literal[1]
    components: dict[str, DictRepositoryComponent]


class DictRepositoryTransaction(TypedDict):
    schemaVersion: Literal[1]
    operation: Literal["publishComponent"]
    state: Literal["prepared", "wheelCommitted"]
    componentId: str
    packageName: str
    version: str
    wheelFile: str
    sha256: str
    targetRelativePath: str
    versionEntry: DictRepositoryComponentVersion


@dataclass(frozen=True)
class RepositoryPublishResult:
    status: Literal["published", "alreadyPublished"]
    warnings: list[DictComponentManagementWarning]


@dataclass(frozen=True)
class RepositoryRebuildResult:
    componentCount: int
    versionCount: int
    warnings: list[DictComponentManagementWarning]


##### Components lock #####


class DictFlowProjectComponentsLockRoot(TypedDict):
    manifestFile: Literal["flow.json"]
    manifestSchemaVersion: Literal[1]
    requiresLiberrpa: str
    componentDependencies: dict[str, str]
    resolutionInputSha256: str


class DictComponentProjectComponentsLockRoot(TypedDict):
    manifestFile: Literal["component.json"]
    manifestSchemaVersion: Literal[1]
    componentId: str
    packageName: str
    requiresLiberrpa: str
    componentDependencies: dict[str, str]
    resolutionInputSha256: str


type DictComponentsLockRoot = DictFlowProjectComponentsLockRoot | DictComponentProjectComponentsLockRoot


class DictLockedComponent(TypedDict):
    manifestSchemaVersion: Literal[1]
    packageName: str
    displayName: str
    version: str
    wheelFile: str
    sha256: str
    requiresLiberrpa: str
    componentDependencies: dict[str, str]


class DictComponentsLockFile(TypedDict):
    """components.lock.json in a Flow or Component Project."""

    schemaVersion: Literal[1]
    root: DictComponentsLockRoot
    components: dict[str, DictLockedComponent]


type ComponentsLockState = Literal["notRequired", "missing", "invalid", "stale", "valid"]
type ComponentsState = Literal["notRequired", "unverified", "missing", "damaged", "valid"]
type EnvironmentState = Literal["unknown", "compatible", "incompatible"]
type RepairState = Literal[
    "notApplicable",
    "available",
    "repositoryUnavailable",
    "wheelMissing",
    "wheelHashMismatch",
]


@dataclass(frozen=True)
class ProjectDependencyState:
    projectPath: Path
    projectType: ProjectType
    manifest: ProjectManifest
    componentsLock: DictComponentsLockFile | None
    lockState: ComponentsLockState
    componentsState: ComponentsState
    environmentState: EnvironmentState
    repairState: RepairState
    details: dict[str, object]


##### Publish #####


class DictPublishResultBase(TypedDict):
    componentId: str
    packageName: str
    astSnippetsFile: str
    snippetsJsoncFile: str
    generatedCount: int
    skippedCount: int
    warningCount: int


class DictPreparationCreatedResult(DictPublishResultBase):
    status: Literal["preparationCreated"]


class DictPublishedComponentResult(DictPublishResultBase):
    status: Literal["published", "alreadyPublished"]
    version: str
    wheelFile: str
    sha256: str
    excludedCount: int
    handWrittenCount: int
    finalCount: int


type DictPublishComponentResult = DictPreparationCreatedResult | DictPublishedComponentResult


class DictRepositoryIndexRebuiltResult(TypedDict):
    status: Literal["repositoryIndexRebuilt"]
    componentCount: int
    versionCount: int


type DictComponentManagementResult = DictPublishComponentResult | DictRepositoryIndexRebuiltResult


##### Protocol #####


class DictPublishComponentRequest(TypedDict):
    schemaVersion: Literal[1]
    operation: Literal["publishComponent"]
    projectPath: str


class DictRebuildRepositoryIndexRequest(TypedDict):
    schemaVersion: Literal[1]
    operation: Literal["rebuildRepositoryIndex"]


type DictComponentManagementRequest = DictPublishComponentRequest | DictRebuildRepositoryIndexRequest


class DictProtocolError(TypedDict):
    code: str
    message: str
    details: dict[str, object]


class DictPublishComponentSuccessResponse(TypedDict):
    schemaVersion: Literal[1]
    ok: Literal[True]
    result: DictPublishComponentResult
    warnings: list[DictComponentManagementWarning]


class DictRepositoryIndexRebuiltSuccessResponse(TypedDict):
    schemaVersion: Literal[1]
    ok: Literal[True]
    result: DictRepositoryIndexRebuiltResult
    warnings: list[DictComponentManagementWarning]


type DictSuccessResponse = DictPublishComponentSuccessResponse | DictRepositoryIndexRebuiltSuccessResponse


class DictErrorResponse(TypedDict):
    schemaVersion: Literal[1]
    ok: Literal[False]
    error: DictProtocolError


type DictProtocolResponse = DictSuccessResponse | DictErrorResponse
