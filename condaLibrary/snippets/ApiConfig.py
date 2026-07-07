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


# Managed import block configuration for liberrpa-snippets-tree.
# Keep this order aligned with liberrpa.Modules.__all__.
MANAGED_IMPORT_SOURCE = "liberrpa.Modules"

MANAGED_IMPORT_ORDER = [
    "Log",
    "delay",
    *PUBLIC_MODULE_ORDER,
    "DatabaseConnection",
    "PrjArgs",
    "CustomArgs",
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


# Import requirements for snippets that are not generated from normal public functions.
# This includes snippets_basic.snippets, generated Log snippets, and SPECIAL_SNIPPETS above.
# Snippets that do not need LiberRPA imports, such as control-flow snippets or a full new-file template,
# should not be listed here.
MANUAL_SNIPPET_IMPORTS: dict[str, list[str]] = {
    "Basic.delay": ["delay"],
    "LogicControl.retry": ["Log"],
    "Log.verbose": ["Log"],
    "Log.verbose_pretty": ["Log"],
    "Log.debug": ["Log"],
    "Log.debug_pretty": ["Log"],
    "Log.info": ["Log"],
    "Log.info_pretty": ["Log"],
    "Log.warning": ["Log"],
    "Log.warning_pretty": ["Log"],
    "Log.error": ["Log"],
    "Log.error_pretty": ["Log"],
    "Log.critical": ["Log"],
    "Log.critical_pretty": ["Log"],
    "Log.exception_info": ["Log"],
    "Log.set_level": ["Log"],
    "Log.add_custom_log_part": ["Log"],
    "Log.remove_custom_log_part": ["Log"],
    "Log.trace": ["Log"],
    "Database.build database connection": ["DatabaseConnection"],
    "FTP.build FTP connection": ["FTP"],
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
