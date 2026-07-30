# FileName: _Warning.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from typing import NotRequired, TypedDict


class DictComponentManagementWarning_Operation(TypedDict):
    code: str
    message: str
    details: NotRequired[dict[str, object]]


class DictComponentManagementWarning_SnippetDiagnostic(TypedDict):
    code: str
    file: str
    line: int
    functionName: NotRequired[str]
    message: str


class DictComponentManagementWarning_SnippetConfig(TypedDict):
    code: str
    message: str
    snippetKey: str


type DictComponentManagementWarning = (
    DictComponentManagementWarning_SnippetDiagnostic
    | DictComponentManagementWarning_SnippetConfig
    | DictComponentManagementWarning_Operation
)
