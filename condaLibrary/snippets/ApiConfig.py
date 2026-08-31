# FileName: ApiConfig.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

"""Shared configuration for LiberRPA API, snippet, and catalog generation."""

from typing import Literal, NotRequired, TypedDict

type SnippetInsertionMode = Literal["line", "cursor"]

type DictSnippetImports = dict[str, list[str]]


class DictSnippetsItem(TypedDict):
    prefix: str
    body: list[str] | str
    description: NotRequired[str]

    label: NotRequired[str]
    imports: NotRequired[DictSnippetImports]

    insertionMode: NotRequired[SnippetInsertionMode]


class DictCatalogSnippet(TypedDict):
    category: str
    label: str

    prefix: str
    body: list[str]
    description: str

    imports: NotRequired[DictSnippetImports]
    insertionMode: SnippetInsertionMode


class DictImportSourceConfig(TypedDict):
    order: list[str]
    aliasMode: NotRequired[Literal["source_module"]]


class DictSnippetsCatalog(TypedDict):
    schemaVersion: Literal[1]
    categoryOrder: list[str]
    categoryIcons: dict[str, str]
    importSources: dict[str, DictImportSourceConfig]
    snippets: dict[str, DictCatalogSnippet]


# Public modules that should be scanned for normal function snippets.
#
# Do not include Log, delay, PrjArgs, CustomArgs, or helper classes here.
# They are user-facing import targets, but they are not normal
# liberrpa.<Module> function modules to scan.
PUBLIC_MODULE_ORDER = [
    # UI element manipulation
    "Mouse",
    "Keyboard",
    "Window",
    "UiInterface",
    # Common software manipulation
    "Browser",
    "Excel",
    "Outlook",
    "Application",
    "Database",
    # Data processing
    "Data",
    "Str",
    "List",
    "Dict",
    "Regex",
    "Math",
    "Time",
    "File",
    "OCR",
    # Web protocol
    "Web",
    "Mail",
    "FTP",
    # System information
    "Clipboard",
    "System",
    "Credential",
    # User interaction
    "ScreenPrint",
    "Dialog",
    "Trigger",
]


# Category order in the snippets tree. Favorite is added by the extension at runtime.
SNIPPET_CATEGORY_ORDER = [
    "Project Values",
    "Basic",
    "LogicControl",
    "Log",
    *PUBLIC_MODULE_ORDER,
]


# VS Code Product Icon IDs for built-in Snippet categories.
# The identifiers are documented at:
# https://code.visualstudio.com/api/references/icons-in-labels#icon-listing
# Note that using the identifiers in the second table of the chapter "Icon Listing".
SNIPPET_CATEGORY_ICON: dict[str, str] = {
    "Project Values": "symbol-variable",
    #
    "Basic": "circle-large-outline",
    "LogicControl": "git-compare",
    "Log": "pencil",
    #
    "Mouse": "inspect",
    "Keyboard": "keyboard",
    "Window": "multiple-windows",
    "UiInterface": "target",
    #
    "Browser": "globe",
    "Excel": "book",
    "Outlook": "mail-read",
    "Application": "circuit-board",
    "Database": "database",
    #
    "Data": "file-binary",
    "Str": "symbol-text",
    "List": "symbol-array",
    "Dict": "json",
    "Regex": "regex",
    "Math": "symbol-operator",
    "Time": "calendar",
    "File": "request-changes",
    "OCR": "search-fuzzy",
    #
    "Web": "cloud",
    "Mail": "mail",
    "FTP": "references",
    #
    "Clipboard": "clippy",
    "System": "terminal",
    "Credential": "key",
    #
    "ScreenPrint": "info",
    "Dialog": "bell",
    "Trigger": "rocket",
}


# Managed import block configuration for liberrpa-snippets-tree.
# Keep this order aligned with liberrpa.Modules.__all__.
MANAGED_IMPORT_SOURCE = "liberrpa.Modules"

MANAGED_IMPORT_ORDER = [
    "Log",
    "delay",
    "get_component_resource_path",
    *PUBLIC_MODULE_ORDER,
    "DatabaseConnection",
    "PrjArgs",
    "CustomArgs",
    #
    "SelectorWindow",
    "SelectorUia",
    "SelectorHtml",
    "SelectorImage",
    "Selector",
]

# Some public functions should not be exposed as snippets.
SKIP_FUNCTIONS: dict[str, set[str]] = {
    # "Trigger": {"register_force_exit"}, Its name has been modified.
}

# Snippets that cannot be generated directly from public functions.
# They are inserted under their module according to PUBLIC_MODULE_ORDER.
SPECIAL_SNIPPETS: dict[str, dict[str, DictSnippetsItem]] = {
    "Database": {
        "Database.build database connection": {
            "prefix": "Database.build database connection",
            "body": [
                "with DatabaseConnection(connectString=${1:None}, dbType=${2:None}, username=${3:None}, password=${4:None}, host=${5:None}, port=${6:None}, database=${7:None}, options={$8}) as ${9:connObj}:",
                "\t$10",
            ],
            "description": "Create a DatabaseConnection context manager. See liberrpa.Database.DatabaseConnection's docstring for details.",
            "imports": {MANAGED_IMPORT_SOURCE: ["DatabaseConnection"]},
        },
    },
    "FTP": {
        "FTP.build FTP connection": {
            "prefix": "FTP.build FTP connection",
            "body": [
                'with FTP.Host(host=$1, user=$2, passwd=$3, encoding=${4:"utf-8"}) as ${5:ftpObj}:',
                "\t$6",
            ],
            "description": "Create an ftputil.FTPHost context manager. See ftputil.FTPHost documentation for details.",
            "imports": {MANAGED_IMPORT_SOURCE: ["FTP"]},
        },
    },
}


# Common object parameter names should get meaningful default placeholders.
PARAMETER_PLACEHOLDER_NAMES = {
    "browserObj": "browserObj",
    "excelObj": "excelObj",
    "screenPrintObj": "screenPrintObj",
    "connObj": "connObj",
    "imapObj": "imapObj",
    "ftpObj": "ftpObj",
    "emailObj": "emailObj",
}

# Exact return annotation strings that should use stable variable names.
RETURN_PLACEHOLDER_BY_ANNOTATION = {
    "<class 'liberrpa.Browser.BrowserObj'>": "browserObj",
    "<class 'liberrpa.Common._Excel.ExcelObj'>": "excelObj",
    "<class 'liberrpa.ScreenPrint.ScreenPrintObj'>": "screenPrintObj",
    "<class 'imapclient.imapclient.IMAPClient'>": "imapObj",
    "<class 'str'>": "strResult",
    "<class 'int'>": "intResult",
    "<class 'float'>": "floatResult",
    "<class 'bool'>": "boolResult",
    "str": "strResult",
    "int": "intResult",
    "float": "floatResult",
    "bool": "boolResult",
}
