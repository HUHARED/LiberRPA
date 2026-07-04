# FileName: HandleLogger.py


"""Generate Log snippets from liberrpa.Logging.Logger docstrings.

This script is intentionally separate from the main snippet generation pipeline because
Log is a special user-facing object, not a normal module. It keeps snippet descriptions
synchronized with Logger method docstrings while keeping snippet bodies compact.

Normal log methods support print-like *messages and sep, but snippets intentionally use
the compact form:

    Log.info($1)

Users can still manually write:

    Log.info("a", "b", sep=" | ")
"""

from __future__ import annotations

import inspect
from typing import Any

from ApiConfig import DictSnippetsItem
from SnippetUtils import get_snippets_dir, write_json
from liberrpa.Logging import Logger


# Keep this close to the old hand-written order.
LOG_SNIPPET_ORDER = [
    "verbose",
    "verbose_pretty",
    "debug",
    "debug_pretty",
    "info",
    "info_pretty",
    "warning",
    "warning_pretty",
    "error",
    "error_pretty",
    "critical",
    "critical_pretty",
    "exception_info",
    "set_level",
    "add_custom_log_part",
    "remove_custom_log_part",
    "trace",
]

# These methods are internal helpers or are not useful as snippets.
SKIP_LOG_METHODS = {
    "_build_human_format",
    "_build_human_message",
    "_build_machine_message",
    "_create_logger",
    "_format",
    "_get_console_formatter",
    "_get_custom_log_parts",
    "_get_human_formatter",
    "_get_json_formatter",
    "_refresh_loggers_format",
    "_trace_call",
    "_write_log",
}


def _get_docstring(func: Any) -> str:
    return inspect.getdoc(func) or ""


def _build_ordered_logger_methods() -> list[tuple[str, Any]]:
    """Return public Logger methods in stable snippet order."""
    result: list[tuple[str, Any]] = []
    used: set[str] = set()

    for name in LOG_SNIPPET_ORDER:
        func = getattr(Logger, name, None)
        if inspect.isfunction(func):
            result.append((name, func))
            used.add(name)

    for name, func in inspect.getmembers(Logger, predicate=inspect.isfunction):
        if name.startswith("_") or name in used or name in SKIP_LOG_METHODS:
            continue
        result.append((name, func))
        used.add(name)

    return result


def _build_log_method_body(method_name: str) -> str:
    """Build compact snippet body for Log methods."""
    if method_name in {
        "verbose",
        "debug",
        "info",
        "warning",
        "error",
        "critical",
        "verbose_pretty",
        "debug_pretty",
        "info_pretty",
        "warning_pretty",
        "error_pretty",
        "critical_pretty",
    }:
        return f"Log.{method_name}($1)"

    if method_name == "exception_info":
        return "Log.exception_info(exObj=$1)"

    if method_name == "set_level":
        return "Log.set_level(level=$1, loggerType=${2:'both'})"

    if method_name == "add_custom_log_part":
        return "Log.add_custom_log_part(name=$1, text=$2)"

    if method_name == "remove_custom_log_part":
        return "Log.remove_custom_log_part(name=$1)"

    if method_name == "trace":
        return "@Log.trace(level=${1:'DEBUG'})"

    # Fallback for future public methods: generate a simple keyword-style call.
    func = getattr(Logger, method_name)
    params = inspect.signature(func).parameters
    parts: list[str] = []
    index = 1

    for param_name, param in params.items():
        if param_name == "self":
            continue

        if param.kind == inspect.Parameter.VAR_POSITIONAL:
            parts.append(f"${index}")
            index += 1
            continue

        if param.kind == inspect.Parameter.VAR_KEYWORD:
            continue

        if param.default is inspect.Parameter.empty:
            parts.append(f"{param_name}=${index}")
        else:
            parts.append(f"{param_name}=${{{index}:{repr(param.default)}}}")

        index += 1

    return f"Log.{method_name}({', '.join(parts)})"


def _generate_log_snippets() -> dict[str, dict[str, DictSnippetsItem]]:
    snippets: dict[str, DictSnippetsItem] = {}

    for name, func in _build_ordered_logger_methods():
        title = f"Log.{name}"
        snippets[title] = {
            "prefix": title,
            "body": _build_log_method_body(method_name=name),
            "description": _get_docstring(func),
        }

    return {"Log": snippets}


def main() -> None:
    snippets_dir = get_snippets_dir()
    write_json(snippets_dir / "snippets_log_generated.snippets", _generate_log_snippets())


if __name__ == "__main__":
    main()
