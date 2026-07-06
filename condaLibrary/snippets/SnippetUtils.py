# FileName: SnippetUtils.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

"""Shared helpers for LiberRPA snippet and API generation scripts."""

from pathlib import Path
import json
import json5
import inspect
from typing import Any, cast


# VS Code snippet choices treat comma and pipe as delimiters.
def _escape_snippet_choice(value: str) -> str:
    """Escape a value used inside VS Code snippet choice syntax."""
    return value.replace("\\", "\\\\").replace(",", "\\,").replace("|", "\\|")


def format_snippet_choice(index: int, choices: list[str]) -> str:
    """Return a VS Code choice placeholder."""
    if not choices:
        raise ValueError("Snippet choices should not be empty.")

    escapedChoices = [_escape_snippet_choice(choice) for choice in choices]
    return f"${{{index}|{','.join(escapedChoices)}|}}"


def unwrap_type_alias(annotation: object) -> object:
    """Return the underlying value of a PEP 695 type alias when available."""
    value = getattr(annotation, "__value__", None)
    if value is None:
        return annotation
    return value


def get_bool_choices(parameter: inspect.Parameter) -> list[str] | None:
    """Return bool snippet choices, keeping the default value first."""
    annotation = unwrap_type_alias(parameter.annotation)

    if annotation is not bool and not isinstance(parameter.default, bool):
        return None

    if parameter.default is inspect.Parameter.empty:
        raise ValueError(
            f"Bool parameter {parameter.name!r} has no default value. "
            "Check whether this is intentional before generating snippets."
        )

    if not isinstance(parameter.default, bool):
        raise ValueError(f"Bool parameter {parameter.name!r} has a non-bool default: {parameter.default!r}")

    if parameter.default is True:
        return ["True", "False"]
    return ["False", "True"]


def find_project_root() -> Path:
    """Return the condaLibrary-style project root containing both liberrpa and snippets."""
    for path in [Path.cwd(), *Path.cwd().parents]:
        if (path / "liberrpa").is_dir() and (path / "snippets").is_dir():
            return path
    raise FileNotFoundError("Could not find project root containing 'liberrpa' and 'snippets' folders.")


def get_snippets_dir() -> Path:
    """Return the snippets folder under the project root."""
    return find_project_root() / "snippets"


def read_json[T](path: Path, valueType: type[T] | None = None) -> T:
    """Read a JSON file and return its parsed value."""
    if not path.is_file():
        raise FileNotFoundError(f"JSON file was not found: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if valueType is not None and not isinstance(value, valueType):
        raise TypeError(f"Expected {path} to contain {valueType.__name__}, got {type(value).__name__}.")
    return cast(T, value)


def read_json5[T](path: Path, valueType: type[T] | None = None) -> T:
    """Read a JSON5 file and return its parsed value."""
    if not path.is_file():
        raise FileNotFoundError(f"JSON5 file was not found: {path}")
    value = json5.loads(path.read_text(encoding="utf-8"))
    if valueType is not None and not isinstance(value, valueType):
        raise TypeError(f"Expected {path} to contain {valueType.__name__}, got {type(value).__name__}.")
    return cast(T, value)


def write_json(path: Path, value: Any) -> None:
    """Write a value as formatted JSON."""
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
