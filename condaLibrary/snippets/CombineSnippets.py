# FileName: CombineSnippets.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

"""Combine manually written snippets and generated snippets into snippets_final.snippets."""

from copy import deepcopy
from typing import cast

from ApiConfig import DictSnippetsItem
from SnippetUtils import get_snippets_dir, read_json5, write_json


def _read_snippet_groups(fileName: str) -> dict[str, dict[str, DictSnippetsItem]]:
    path = get_snippets_dir() / fileName
    return cast(dict[str, dict[str, DictSnippetsItem]], read_json5(path, dict))


def _copy_with_empty_line(item: DictSnippetsItem) -> DictSnippetsItem:
    itemCopy = deepcopy(item)
    body = itemCopy["body"]

    if isinstance(body, str):
        itemCopy["body"] = [body, ""]
    else:
        # As a safety net.
        if len(body) == 0:
            raise ValueError("Snippet body list should not be empty.")

        if body[-1] != "":
            body.append("")

    return itemCopy


def _merge_groups(
    dictFinal: dict[str, DictSnippetsItem],
    snippetGroups: dict[str, dict[str, DictSnippetsItem]],
) -> None:
    for moduleName, group in snippetGroups.items():
        for title, item in group.items():
            if title in dictFinal:
                raise ValueError(f"Duplicate snippet title: {title!r} in group {moduleName!r}.")
            dictFinal[title] = _copy_with_empty_line(item)


def main() -> None:
    snippetsDir = get_snippets_dir()
    dictBasic = _read_snippet_groups("snippets_basic.snippets")
    dictOther = _read_snippet_groups("snippets_other.snippets")

    dictFinal: dict[str, DictSnippetsItem] = {}
    _merge_groups(dictFinal=dictFinal, snippetGroups=dictBasic)
    _merge_groups(dictFinal=dictFinal, snippetGroups=dictOther)

    if not dictFinal:
        raise ValueError("No snippets were generated.")

    write_json(snippetsDir / "snippets_final.snippets", dictFinal)


if __name__ == "__main__":
    main()
