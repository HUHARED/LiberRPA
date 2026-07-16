# FileName: CombineSnippets.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

"""Combine hand-written and generated snippets into snippets_catalog.json."""

from copy import deepcopy
from typing import cast

from ApiConfig import (
    DictCatalogSnippet,
    DictSnippetsCatalog,
    DictSnippetsItem,
    MANAGED_IMPORT_ORDER,
    MANAGED_IMPORT_SOURCE,
    SNIPPET_CATEGORY_ORDER,
)
from SnippetUtils import get_snippets_dir, read_json5, write_json


def _read_snippet_groups(fileName: str) -> dict[str, dict[str, DictSnippetsItem]]:
    path = get_snippets_dir() / fileName
    return cast(dict[str, dict[str, DictSnippetsItem]], read_json5(path, dict))


def _normalize_body(item: DictSnippetsItem) -> list[str]:
    itemCopy = deepcopy(item)
    body = itemCopy["body"]

    if isinstance(body, str):
        bodyLines = [body]
    else:
        if len(body) == 0:
            raise ValueError("Snippet body list should not be empty.")
        bodyLines = list(body)

    if itemCopy.get("appendFinalTabstop", True):
        if bodyLines[-1] == "":
            bodyLines[-1] = "$0"
        elif bodyLines[-1] != "$0":
            bodyLines.append("$0")

    return bodyLines


def _get_default_label(category: str, title: str) -> str:
    prefix = f"{category}."
    if title.startswith(prefix):
        return title[len(prefix) :]
    return title


def _validate_imports(title: str, item: DictSnippetsItem) -> None:
    imports = item.get("imports", {})

    for importSource, importNames in imports.items():
        if importSource != MANAGED_IMPORT_SOURCE:
            raise ValueError(
                f"Snippet {title!r} uses unknown import source {importSource!r}. "
                f"Known source: {MANAGED_IMPORT_SOURCE!r}."
            )

        unknownNames = sorted(set(importNames) - set(MANAGED_IMPORT_ORDER))
        if unknownNames:
            raise ValueError(f"Snippet {title!r} contains unknown import names: {unknownNames}")


def _build_catalog_item(category: str, title: str, item: DictSnippetsItem) -> DictCatalogSnippet:
    _validate_imports(title=title, item=item)

    description = item.get("description")
    if description is None:
        raise ValueError(f"Snippet {title!r} is missing its description.")

    result: DictCatalogSnippet = {
        "category": category,
        "label": item.get("label", _get_default_label(category=category, title=title)),
        "prefix": item["prefix"],
        "body": _normalize_body(item=item),
        "description": description,
        "insertionMode": item.get("insertionMode", "line"),
    }

    imports = item.get("imports")
    if imports:
        result["imports"] = deepcopy(imports)

    return result


def _merge_groups(
    snippets: dict[str, DictCatalogSnippet],
    snippetGroups: dict[str, dict[str, DictSnippetsItem]],
) -> None:
    for category, group in snippetGroups.items():
        if category not in SNIPPET_CATEGORY_ORDER:
            raise ValueError(f"Unknown snippet category: {category!r}.")

        for title, item in group.items():
            if title in snippets:
                raise ValueError(f"Duplicate snippet title: {title!r} in category {category!r}.")

            snippets[title] = _build_catalog_item(category=category, title=title, item=item)


def main() -> None:
    snippetsDir = get_snippets_dir()
    dictBasic = _read_snippet_groups("snippets_basic.snippets")
    dictLog = _read_snippet_groups("snippets_log_generated.snippets")
    dictOther = _read_snippet_groups("snippets_other.snippets")

    snippets: dict[str, DictCatalogSnippet] = {}
    _merge_groups(snippets=snippets, snippetGroups=dictBasic)
    _merge_groups(snippets=snippets, snippetGroups=dictLog)
    _merge_groups(snippets=snippets, snippetGroups=dictOther)

    if not snippets:
        raise ValueError("No snippets were generated.")

    categoryWithSnippets = {item["category"] for item in snippets.values()}
    categoryOrder = [category for category in SNIPPET_CATEGORY_ORDER if category in categoryWithSnippets]

    catalog: DictSnippetsCatalog = {
        "schemaVersion": 1,
        "categoryOrder": categoryOrder,
        "importSources": {
            MANAGED_IMPORT_SOURCE: {
                "order": list(MANAGED_IMPORT_ORDER),
            }
        },
        "snippets": snippets,
    }

    write_json(snippetsDir / "snippets_catalog.json", catalog)


if __name__ == "__main__":
    main()
