# FileName: _SnippetConfig.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from liberrpa.ComponentManagement._Exception import ComponentManagementError
from liberrpa.ComponentManagement._File import write_text_atomic

from pathlib import Path


_PATH_TEMPLATE = Path(__file__).resolve().parent / "Templates/snippets.jsonc.template"


def create_snippet_config(configPath: Path) -> bool:
    if configPath.exists():
        if not configPath.is_file():
            raise ComponentManagementError(
                code="snippet_config_invalid",
                message=f"Snippet configuration path is not a file: {configPath}",
            )
        return False

    try:
        strTemplate = _PATH_TEMPLATE.read_text(encoding="utf-8", errors="strict")
    except OSError as e:
        raise ComponentManagementError(
            code="snippet_template_missing",
            message=f"Failed to read the Component Snippet template: {_PATH_TEMPLATE}",
        ) from e

    if strTemplate.strip() == "":
        raise ComponentManagementError(
            code="snippet_template_invalid",
            message=f"The Component Snippet template is empty: {_PATH_TEMPLATE}",
        )

    try:
        write_text_atomic(path=configPath, text=strTemplate.rstrip("\r\n") + "\n")
    except OSError as e:
        raise ComponentManagementError(
            code="io_error",
            message=f"Failed to create Component Snippet configuration: {configPath}",
        ) from e

    return True
