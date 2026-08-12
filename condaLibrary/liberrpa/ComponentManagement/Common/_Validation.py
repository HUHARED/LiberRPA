# FileName: _Validation.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from pathlib import Path
import keyword
import re
import sys
import uuid


def add_validation_issue(
    issueList: list[dict[str, object]], field: str, message: str
) -> None:
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
        add_validation_issue(issueList, field, f"Unknown fields: {listUnknownKey}.")


_REGEX_INVALID_WINDOWS_FILE_OR_FOLDER_NAME_CHARACTER = re.compile(r'[<>:"/\\|?*]')
_REGEX_COMPONENT_PACKAGE_NAME = re.compile(r"^[A-Z][A-Za-z0-9]*$")

_STR_COMPONENT_ID_FOR_FOLDER_NAME_VALIDATION = "00000000-0000-4000-8000-000000000000"

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


def get_windows_file_or_folder_name_error(
    name: str,
    description: str,
) -> str | None:
    if name == "":
        return f"{description} cannot be empty."

    if name != name.strip():
        return f"{description} cannot start or end with whitespace."

    if _REGEX_INVALID_WINDOWS_FILE_OR_FOLDER_NAME_CHARACTER.search(name) is not None:
        return (
            f"{description} cannot contain Windows reserved characters: " + '<>:"/\\|?*'
        )

    if any(ord(character) <= 0x1F for character in name):
        return f"{description} cannot contain ASCII control characters."

    if name.endswith("."):
        return f"{description} cannot end with a period."

    strNameBeforeFirstPeriod = name.split(".", 1)[0].upper()
    if strNameBeforeFirstPeriod in _SET_RESERVED_WINDOWS_NAMES:
        return f'{description} "{name}" is reserved by Windows.'

    # JavaScript String.length and Windows entry name limits use UTF-16 code units.
    intUtf16CodeUnitCount = len(name.encode("utf-16-le", errors="surrogatepass")) // 2
    if intUtf16CodeUnitCount > 255:
        return f"{description} cannot be longer than 255 characters."

    return None


def get_package_name_error(packageName: str) -> str | None:
    strWindowsNameError = get_windows_file_or_folder_name_error(
        packageName,
        "Package name",
    )
    if strWindowsNameError is not None:
        return strWindowsNameError

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

    strRepositoryFolderName = (
        f"{packageName}_{_STR_COMPONENT_ID_FOR_FOLDER_NAME_VALIDATION}"
    )
    strRepositoryFolderNameError = get_windows_file_or_folder_name_error(
        strRepositoryFolderName,
        "Generated Component Repository folder name",
    )
    if strRepositoryFolderNameError is not None:
        return strRepositoryFolderNameError

    strNormalizedName = packageName.casefold()

    if strNormalizedName == "liberrpa":
        return 'Package name "liberrpa" is reserved by LiberRPA.'

    if strNormalizedName in _SET_PYTHON_STDLIB_MODULE_NAMES:
        return f"Package name {packageName!r} conflicts with a Python standard library module."

    if strNormalizedName in _SET_LIBERRPA_THIRD_PARTY_MODULE_NAMES:
        return f"Package name {packageName!r} conflicts with a third-party package used by LiberRPA."

    return None


def validate_uuid_v4(value: object, field: str) -> str:
    """Validate and return a canonical lowercase UUID v4 string."""
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a UUID string.")

    try:
        uuidObj = uuid.UUID(value)
    except ValueError as e:
        raise ValueError(f"{field} must be a valid UUID.") from e

    if uuidObj.version != 4 or uuidObj.variant != uuid.RFC_4122:
        raise ValueError(f"{field} must be a UUID v4.")

    if value != str(uuidObj):
        raise ValueError(
            f"{field} must use the canonical lowercase UUID format with hyphens."
        )

    return value


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


def is_path_link(entryPath: Path) -> bool:
    """Return whether the path is a symbolic link or Windows junction."""
    return entryPath.is_symlink() or entryPath.is_junction()


def path_exists(entryPath: Path) -> bool:
    """Return whether a filesystem entry exists, including a broken link."""
    return entryPath.exists() or is_path_link(entryPath)


def is_file_invalid(filePath: Path) -> bool:
    """Return whether the path is not a regular non-link file."""
    return not filePath.is_file() or is_path_link(filePath)


def is_folder_invalid(folderPath: Path) -> bool:
    """Return whether the path is not a regular non-link folder."""
    return not folderPath.is_dir() or is_path_link(folderPath)
