# FileName: _Utils.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from liberrpa.Common._TypedValue import StrPath

from pathlib import Path, PureWindowsPath
import os
import re
import multiprocessing

# Use it to replace all os.getcwd(), to avoid influence caused by os.chdir() that users execute.
PATH_PROJECT_ROOT = Path.cwd().resolve()
STR_PROJECT_ROOT: str = str(PATH_PROJECT_ROOT)
PATH_PROJECT_JSON = PATH_PROJECT_ROOT / "project.json"
PATH_PROJECT_FLOW = PATH_PROJECT_ROOT / "project.flow"

PROCESS_NAME = multiprocessing.current_process().name


def _normalize_filepath(filePath: StrPath) -> str:
    """
    Normalize path string for logs/config display.
    - Windows absolute path: G:\\foo\\bar -> G:/foo/bar
    - POSIX path: /foo/bar -> /foo/bar
    - Relative path: foo\\bar -> ./foo/bar
    - Existing ./ or ../ is preserved
    """

    path = os.fspath(filePath).strip()

    if not path:
        return "."

    # Windows drive path, for example: C:\foo, C:/foo, C:foo
    if re.match(r"^[a-zA-Z]:[\\/]", path):
        return PureWindowsPath(path).as_posix()

    # UNC path, for example: \\server\share\file
    if path.startswith("\\\\"):
        return PureWindowsPath(path).as_posix()

    normalized = path.replace("\\", "/")

    if normalized.startswith(("/", "./", "../")):
        return normalized

    return f"./{normalized}"


if __name__ == "__main__":
    cases = [
        "file.name",
        "./file.name",
        "../file.name",
        r"dir\file.name",
        r"G:\OneDrive\LiberRPA\file.name",
        "/home/user/file.name",
        r"\\server\share\file.name",
    ]

    for item in cases:
        print("===")
        print(Path(Path.cwd()) / _normalize_filepath(item))
        print(f"{item!r} -> {_normalize_filepath(item)}")
