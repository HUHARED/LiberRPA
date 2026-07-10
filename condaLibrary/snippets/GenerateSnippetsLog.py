# FileName: GenerateSnippetsLog.py
"""Generate Log snippets from liberrpa.Logging.Logger docstrings.

Log is a special user-facing object, not a normal liberrpa.<Module> function module.
This script keeps Log snippet descriptions synchronized with Logger method docstrings
while keeping snippet bodies compact.

Normal log methods support print-like *messages and sep, but snippets intentionally use
the compact form:

    Log.info($1)

Users can still manually write:

    Log.info("a", "b", sep=" | ")

The generated snippets_log_generated.snippets file is merged by CombineSnippets.py.
"""

from __future__ import annotations

__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import inspect
from typing import Any

from ApiConfig import DictSnippetsItem, MANAGED_IMPORT_SOURCE
from SnippetUtils import format_snippet_choice, format_string_choices, get_snippet_choices, get_snippets_dir, write_json
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

LOG_LEVEL_VALUES = ["VERBOSE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LOGGER_TYPE_VALUES = ["both", "human", "machine"]


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
        # exObj has no default value. Use a bare tab stop instead of placeholder
        # text, otherwise the snippet may look like the function has a default.
        return "Log.exception_info(exObj=$1)"

    if method_name == "set_level":
        # level has no function default. Keep the annotation/order-defined choices
        # instead of moving any value to the first position as a fake default.
        levelChoice = format_string_choices(index=1, values=LOG_LEVEL_VALUES)
        loggerTypeChoice = format_string_choices(index=2, values=LOGGER_TYPE_VALUES, default="both")
        return f"Log.set_level(level={levelChoice}, loggerType={loggerTypeChoice})"

    if method_name == "add_custom_log_part":
        # name and text have no default values. Keep them as bare tab stops.
        return "Log.add_custom_log_part(name=$1, text=$2)"

    if method_name == "remove_custom_log_part":
        # name has no default value. Keep it as a bare tab stop.
        return "Log.remove_custom_log_part(name=$1)"

    if method_name == "trace":
        levelChoice = format_string_choices(index=1, values=LOG_LEVEL_VALUES, default="DEBUG")
        return f"@Log.trace(level={levelChoice})"

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

        snippetChoices = get_snippet_choices(parameter=param)
        if snippetChoices:
            parts.append(f"{param_name}={format_snippet_choice(index=index, choices=snippetChoices)}")
        elif param.default is inspect.Parameter.empty:
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
            "imports": {MANAGED_IMPORT_SOURCE: ["Log"]},
        }

    return {"Log": snippets}


def main() -> None:
    snippets_dir = get_snippets_dir()
    write_json(snippets_dir / "snippets_log_generated.snippets", _generate_log_snippets())


if __name__ == "__main__":
    main()
