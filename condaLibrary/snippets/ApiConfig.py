# FileName: ApiConfig.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

"""Shared configuration for LiberRPA API, snippet, and import-manifest generation."""

from typing import TypedDict, NotRequired


class DictSnippetsItem(TypedDict):
    prefix: str
    body: list[str] | str
    description: NotRequired[str]


# Keep this order aligned with liberrpa.Modules. It is used by API docs,
# generated snippets, and the future snippets-tree import manager.
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

# Some public functions should not be exposed as snippets.
SKIP_FUNCTIONS: dict[str, set[str]] = {
    "Trigger": {"register_force_exit"},
}

# Snippets that cannot be generated directly from public functions.
# They are inserted under their module according to PUBLIC_MODULE_ORDER.
SPECIAL_SNIPPETS: dict[str, dict[str, dict[str, object]]] = {
    "Database": {
        "Database.build database connection": {
            "prefix": "Database.build database connection",
            "body": [
                "with DatabaseConnection(connectString=${1:None}, dbType=${2:None}, username=${3:None}, password=${4:None}, host=${5:None}, port=${6:None}, database=${7:None}, options={$8}) as ${9:connObj}:",
                "\t$10",
            ],
            "description": "Create a DatabaseConnection context manager. See liberrpa.Database.DatabaseConnection's docstring for details.",
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
    "<class 'liberrpa.Excel.ExcelObj'>": "excelObj",
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
