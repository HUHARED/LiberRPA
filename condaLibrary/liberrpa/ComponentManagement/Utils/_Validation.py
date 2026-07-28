# FileName: _Validation.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


import keyword
import re
import sys


def add_issue(issueList: list[dict[str, object]], field: str, message: str) -> None:
    issueList.append({"field": field, "message": message})


def validate_json_object_fields(
    value: dict[object, object],
    allowedKeys: set[str],
    field: str,
    issueList: list[dict[str, object]],
) -> None:
    listUnknownKey: list[str] = []

    for key in value:
        if not isinstance(key, str):
            listUnknownKey.append(repr(key))
        elif key not in allowedKeys:
            listUnknownKey.append(key)

    listUnknownKey.sort()

    if listUnknownKey:
        add_issue(issueList, field, f"Unknown fields: {listUnknownKey}.")


_REGEX_COMPONENT_PACKAGE_NAME = re.compile(r"^[A-Z][A-Za-z0-9]*$")

_SET_RESERVED_WINDOWS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}

_SET_PYTHON_STDLIB_MODULE_NAMES = {name.casefold() for name in sys.stdlib_module_names}

_SET_LIBERRPA_THIRD_PARTY_MODULE_NAMES = {
    name.casefold()
    for name in {
        "psutil",
        "PIL",
        "win32clipboard",
        "win32cred",
        "win32gui",
        "win32con",
        "win32com",
        "win32api",
        "pythoncom",
        "pyperclip",
        "pathvalidate",
        "sqlalchemy",
        "pandas",
        "xlwings",
        "pyzipper",
        "pypdf",
        "fitz",
        "ftputil",
        "uiautomation",
        "pynput",
        "pyautogui",
        "imapclient",
        "mailparser",
        "yagmail",
        "json5",
        "easyocr",
        "requests",
        "screeninfo",
        "socketio",
        "flask",
        "flask_socketio",
        "keyboard",
        "pyWinhook",
        "pystray",
        "mss",
        "PyQt5",
    }
}


def get_package_name_error(packageName: str) -> str | None:
    if _REGEX_COMPONENT_PACKAGE_NAME.fullmatch(packageName) is None:
        return "Package name must use PascalCase and contain only ASCII letters and digits, for example: ExcelTools."

    # These checks intentionally overlap with the current PascalCase naming rule.
    # Keep them independent so future changes to the naming convention don't accidentally allow a package name that isn't a valid Python identifier or is reserved by Python.
    if not packageName.isidentifier():
        return "Package name must be a valid Python identifier."

    # Keep these names explicit even though keyword.iskeyword() also rejects them in Python 3.13, so this rule remains visible and independently enforced.
    if packageName in {"False", "None", "True"}:
        return f"Package name cannot use the reserved Python name {packageName!r}."

    if keyword.iskeyword(packageName):
        return f"Package name cannot use the Python keyword {packageName!r}."

    strNormalizedName = packageName.casefold()

    if strNormalizedName == "liberrpa":
        return 'Package name "liberrpa" is reserved by LiberRPA.'

    if packageName.upper() in _SET_RESERVED_WINDOWS_NAMES:
        return f"Package name {packageName!r} is reserved by Windows."

    if strNormalizedName in _SET_PYTHON_STDLIB_MODULE_NAMES:
        return f"Package name {packageName!r} conflicts with a Python standard library module."

    if strNormalizedName in _SET_LIBERRPA_THIRD_PARTY_MODULE_NAMES:
        return f"Package name {packageName!r} conflicts with a third-party package used by LiberRPA."

    return None


def validate_exact_keys(
    value: dict[object, object],
    expectedKeys: set[str],
    field: str,
) -> None:
    setStringKey = {key for key in value if isinstance(key, str)}
    listNonStringKey = sorted(repr(key) for key in value if not isinstance(key, str))
    listMissingKey = sorted(expectedKeys - setStringKey)
    listUnknownKey = sorted(setStringKey - expectedKeys)

    if listNonStringKey or listMissingKey or listUnknownKey:
        raise ValueError(
            f"{field} has invalid fields. Missing: {listMissingKey}; "
            f"unknown: {listUnknownKey}; non-string: {listNonStringKey}."
        )
