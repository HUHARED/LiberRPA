# FileName: _TypedValue.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from pathlib import Path
from dataclasses import dataclass
from typing import Literal, NotRequired, TypedDict


##### Manifest #####


@dataclass(frozen=True)
class ComponentManifest:
    """component.json in a Component Project"""

    schemaVersion: int
    id: str
    packageName: str
    displayName: str
    version: str
    description: str
    requiresLiberrpa: str
    componentDependencies: dict[str, str]


##### Snippet attributes #####


type SnippetInsertionMode = Literal["line", "cursor"]
type DictSnippetImports = dict[str, list[str]]  # "SourceName": ["ModuleName1", "ModuleName2", ...]


class DictAstSnippet(TypedDict):
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
    snippets: dict[str, DictAstSnippet]
    skipped: list[DictSnippetDiagnostic]
    warnings: list[DictSnippetDiagnostic]


class DictImportSourceConfig(TypedDict):
    order: list[str]
    aliasMode: NotRequired[Literal["source_module"]]


class DictSnippetCatalogFile(TypedDict):
    """snippets.jsonc.template, _Snippets/snippets.jsonc"""

    schemaVersion: Literal[1]
    categoryOrder: list[str]
    importSources: dict[str, DictImportSourceConfig]
    snippets: dict[str, DictAstSnippet]


class DictAstSnippetOverride(TypedDict):
    label: NotRequired[str]
    body: NotRequired[list[str]]
    description: NotRequired[str]
    insertionMode: NotRequired[SnippetInsertionMode]
    imports: NotRequired[DictSnippetImports]


class DictSnippetConfigWarning(TypedDict):
    code: str
    snippetKey: str
    message: str


##### Wheel #####


@dataclass(frozen=True)
class WheelBuildResult:
    wheelPath: Path
    wheelFile: str
    sha256: str


##### Repository #####


class DictRepositoryComponentVersion(TypedDict):
    version: str
    displayName: str
    description: str
    manifestSchemaVersion: int
    wheelFile: str
    sha256: str
    requiresLiberrpa: str
    componentDependencies: dict[str, str]


class DictRepositoryComponent(TypedDict):
    packageName: str
    versions: list[DictRepositoryComponentVersion]


class DictRepositoryIndex(TypedDict):
    schemaVersion: int
    components: dict[str, DictRepositoryComponent]


class DictRepositoryTransaction(TypedDict):
    schemaVersion: int
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
    warnings: list[dict[str, object]]


##### Protocol #####


class DictProtocolError(TypedDict):
    code: str
    message: str
    details: dict[str, object]


class DictSuccessResponse(TypedDict):
    schemaVersion: Literal[1]
    ok: Literal[True]
    result: dict[str, object]
    warnings: list[dict[str, object]]


class DictErrorResponse(TypedDict):
    schemaVersion: Literal[1]
    ok: Literal[False]
    error: DictProtocolError


type DictProtocolResponse = DictSuccessResponse | DictErrorResponse
