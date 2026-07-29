# FileName: _Record.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.ComponentManagement.Utils._Hash import calculate_record_hash

from collections.abc import Callable
from csv import reader
from io import StringIO
import re


_REGEX_WINDOWS_DRIVE_PATH = re.compile(r"^[A-Za-z]:")


def validate_archive_path(archivePath: str) -> None:
    if archivePath == "" or archivePath.endswith("/"):
        raise ValueError(f"Wheel contains an invalid file path: {archivePath!r}.")

    if "\x00" in archivePath:
        raise ValueError(f"Wheel path contains a null character: {archivePath!r}.")

    if "\\" in archivePath:
        raise ValueError(f"Wheel path must use '/' separators: {archivePath!r}.")

    if archivePath.startswith("/") or _REGEX_WINDOWS_DRIVE_PATH.match(archivePath):
        raise ValueError(f"Wheel path must be relative: {archivePath!r}.")

    listPathPart = archivePath.split("/")

    if any(pathPart in {"", ".", ".."} for pathPart in listPathPart):
        raise ValueError(f"Wheel contains an unsafe path: {archivePath!r}.")


def validate_record(
    archivePathSet: set[str],
    recordPath: str,
    readArchiveFile: Callable[[str], bytes],
) -> None:
    try:
        strRecord = readArchiveFile(recordPath).decode("utf-8", errors="strict")
    except (KeyError, OSError, UnicodeDecodeError) as e:
        raise ValueError("Wheel RECORD is missing or is not valid UTF-8.") from e

    listRow = list(reader(StringIO(strRecord, newline="")))
    dictRecordRow: dict[str, tuple[str, str]] = {}

    for row in listRow:
        if len(row) != 3:
            raise ValueError("Every Wheel RECORD row must contain exactly three fields.")

        strPath, strHash, strSize = row
        validate_archive_path(strPath)

        if strPath in dictRecordRow:
            raise ValueError(f"Wheel RECORD contains a duplicate path: {strPath!r}.")

        dictRecordRow[strPath] = (strHash, strSize)

    if set(dictRecordRow) != archivePathSet:
        listMissingPath = sorted(archivePathSet - set(dictRecordRow))
        listUnknownPath = sorted(set(dictRecordRow) - archivePathSet)
        raise ValueError(
            "Wheel RECORD paths do not match the Wheel contents. "
            f"Missing: {listMissingPath}; unknown: {listUnknownPath}."
        )

    for strPath in sorted(archivePathSet):
        strHash, strSize = dictRecordRow[strPath]

        if strPath == recordPath:
            if strHash != "" or strSize != "":
                raise ValueError("The Wheel RECORD row for RECORD itself must have empty hash and size fields.")
            continue

        value = readArchiveFile(strPath)
        if strHash != calculate_record_hash(value):
            raise ValueError(f"Wheel RECORD hash does not match: {strPath!r}.")

        if strSize != str(len(value)):
            raise ValueError(f"Wheel RECORD size does not match: {strPath!r}.")
