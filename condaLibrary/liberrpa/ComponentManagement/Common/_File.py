# FileName: _File.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from pathlib import Path
import json
import json5
import os
import uuid


class DuplicateJsonKeyError(ValueError):
    pass


def _build_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    dictResult: dict[str, object] = {}

    for strKey, value in pairs:
        if strKey in dictResult:
            raise DuplicateJsonKeyError(f"Duplicate JSON key: {strKey!r}.")

        dictResult[strKey] = value

    return dictResult


def parse_json(value: str) -> object:
    try:
        return json.loads(value, object_pairs_hook=_build_json_object)
    except DuplicateJsonKeyError:
        raise
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}.") from e


def read_json(path: Path) -> object:
    try:
        return parse_json(path.read_text(encoding="utf-8", errors="strict"))
    except ValueError as e:
        raise ValueError(f"Invalid JSON file {path}: {e}.") from e


def _parse_jsonc(value: str) -> object:
    try:
        return json5.loads(value, allow_duplicate_keys=False)
    except ValueError as e:
        raise ValueError(f"Invalid JSONC: {e}.") from e


def read_jsonc(path: Path) -> object:
    try:
        return _parse_jsonc(path.read_text(encoding="utf-8", errors="strict"))
    except ValueError as e:
        raise ValueError(f"Invalid JSONC file {path}: {e}.") from e


def serialize_json(value: object, *, compact: bool = False) -> str:
    if compact:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pathTemp = path.parent / f".{path.name}.{uuid.uuid4()}.tmp"

    try:
        with pathTemp.open("x", encoding="utf-8", newline="\n") as fileObj:
            fileObj.write(text)
            fileObj.flush()
            os.fsync(fileObj.fileno())

        os.replace(pathTemp, path)
    finally:
        pathTemp.unlink(missing_ok=True)


def write_json_atomic(path: Path, value: object) -> None:
    write_text_atomic(path=path, text=serialize_json(value))
