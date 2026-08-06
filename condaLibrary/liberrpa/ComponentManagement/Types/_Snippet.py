# FileName: _Snippet.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Types._Warning import (
    DictComponentManagementWarning_SnippetDiagnostic,
)


from typing import Literal, NotRequired, TypedDict


type Str_SnippetInsertionMode = Literal["line", "cursor"]
type DictSnippet_Imports = dict[
    str, list[str]
]  # "SourceName": ["ModuleName1", "ModuleName2", ...]


class DictSnippet_Normalized(TypedDict):
    category: str
    label: str

    prefix: str
    body: list[str]
    description: str

    insertionMode: Str_SnippetInsertionMode
    imports: DictSnippet_Imports


class DictSnippet_AstFile(TypedDict):
    """_Snippets/ast.snippets.json"""

    schemaVersion: Literal[1]
    componentId: str
    packageName: str
    snippets: dict[str, DictSnippet_Normalized]
    skipped: list[DictComponentManagementWarning_SnippetDiagnostic]
    warnings: list[DictComponentManagementWarning_SnippetDiagnostic]


class DictSnippet_ImportSourceConfig(TypedDict):
    order: list[str]
    aliasMode: NotRequired[Literal["source_module"]]


class DictSnippet_CatalogFile(TypedDict):
    """snippets_catalog.json in a Component Wheel."""

    schemaVersion: Literal[1]
    categoryOrder: list[str]
    importSources: dict[str, DictSnippet_ImportSourceConfig]
    snippets: dict[str, DictSnippet_Normalized]


class DictSnippet_AstOverride(TypedDict):
    label: NotRequired[str]
    body: NotRequired[list[str]]
    description: NotRequired[str]
    insertionMode: NotRequired[Str_SnippetInsertionMode]
    imports: NotRequired[DictSnippet_Imports]
