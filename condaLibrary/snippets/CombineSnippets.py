# FileName: CombineSnippets.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from pathlib import Path
import json5
from typing import TypedDict, NotRequired, cast
import json
import sys


class DictSnippetsItem(TypedDict):
    prefix: str
    body: list[str] | str
    description: NotRequired[str]


strBasic = Path("./snippets/snippets_basic.snippets").read_text()
strOther = Path("./snippets/snippets_other.snippets").read_text()

dictBasic = cast(dict[str, dict[str, DictSnippetsItem]], json5.loads(strBasic))
dictOther = cast(dict[str, dict[str, DictSnippetsItem]], json5.loads(strOther))

dictFinal: dict[str, DictSnippetsItem] = {}


def _append_empty_line_to_snippet_body(item: DictSnippetsItem) -> None:
    body = item["body"]

    if isinstance(body, str):
        item["body"] = [body, ""]
    else:
        body.append("")


for strModuleName in dictBasic:
    for strTitle in dictBasic[strModuleName]:
        # Add a new line, otherwise vscode will add a cursor postion at the line end. Add a new cursor in the new line is more reasonable.
        try:
            _append_empty_line_to_snippet_body(dictBasic[strModuleName][strTitle])
        except Exception:
            print("Error at", dictBasic[strModuleName][strTitle])
            sys.exit()

        dictFinal[strTitle] = dictBasic[strModuleName][strTitle]

for strModuleName in dictOther:
    for strTitle in dictOther[strModuleName]:
        try:
            _append_empty_line_to_snippet_body(dictOther[strModuleName][strTitle])
        except Exception:
            print("Error at", dictOther[strModuleName][strTitle])
            sys.exit()
        dictFinal[strTitle] = dictOther[strModuleName][strTitle]

strFinal = json.dumps(dictFinal, indent=2, ensure_ascii=False)

if strFinal:
    Path("./snippets/snippets_final.snippets").write_text(strFinal)
else:
    raise Exception("Error.")
