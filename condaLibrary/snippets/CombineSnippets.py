# FileName: CombineSnippets.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"



from pathlib import Path
import json5
from typing import TypedDict, NotRequired
import json
import sys


class DictSnippetsItem(TypedDict):
    prefix: str
    body: list[str] | str
    description: NotRequired[str]


strBasic = Path("./snippets/snippets_basic.snippets").read_text()
strOther = Path("./snippets/snippets_other.snippets").read_text()

dictBasic: dict[str, dict[str, DictSnippetsItem]] = json5.loads(strBasic)  # type: ignore
dictOther: dict[str, dict[str, DictSnippetsItem]] = json5.loads(strOther)  # type: ignore

dictFinal: dict[str, DictSnippetsItem] = {}

for strModuleName in dictBasic:
    for strTitle in dictBasic[strModuleName]:
        # Add a new line, otherwise vscode will add a cursor postion at the line end. Add a new cursor in the new line is more reasonable.
        try:
            if isinstance(dictBasic[strModuleName][strTitle]["body"], str):
                dictBasic[strModuleName][strTitle]["body"] = [dictBasic[strModuleName][strTitle]["body"], ""]  # type: ignore - Convert body to list
            else:
                dictBasic[strModuleName][strTitle]["body"].append("")  # type: ignore - It's list.
        except Exception as e:
            print("Error at", dictBasic[strModuleName][strTitle])
            sys.exit()

        dictFinal[strTitle] = dictBasic[strModuleName][strTitle]

for strModuleName in dictOther:
    for strTitle in dictOther[strModuleName]:
        try:
            if isinstance(dictOther[strModuleName][strTitle]["body"], str):
                dictOther[strModuleName][strTitle]["body"] = [dictOther[strModuleName][strTitle]["body"], ""]  # type: ignore - Convert body to list
            else:
                dictOther[strModuleName][strTitle]["body"].append("")  # type: ignore - It's list.
        except Exception as e:
            print("Error at", dictOther[strModuleName][strTitle])
            sys.exit()
        dictFinal[strTitle] = dictOther[strModuleName][strTitle]

strFinal = json.dumps(dictFinal, indent=2, ensure_ascii=False)

if strFinal:
    Path("./snippets/snippets_final.snippets").write_text(strFinal)
else:
    raise Exception("Error.")

