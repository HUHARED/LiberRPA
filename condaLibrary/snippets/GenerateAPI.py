# FileName: GenerateAPI.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"
from liberrpa.Logging import Log
import liberrpa.Regex as Regex

import json
from pathlib import Path

from typing import TypedDict, NotRequired

Log.set_level("INFO")


class DictSnippetsItem(TypedDict):
    prefix: str
    body: list[str] | str
    description: NotRequired[str]


strContent = Path("./snippets/snippets_final.snippets").read_text(encoding="utf-8")
dictSnippets: dict[str, DictSnippetsItem] = json.loads(strContent)

listModuleNameCache = []

strAPI = ""

for strTitle in dictSnippets:
    print(strTitle)
    listSplitTitle = strTitle.split(".", maxsplit=1)
    # print(listSplitTitle)
    if listSplitTitle[0] not in listModuleNameCache:
        listModuleNameCache.append(listSplitTitle[0])
        strAPI += "## " + listSplitTitle[0] + "\n\n"

    strAPI += "### " + listSplitTitle[1] + "\n\n"

    strDescription = dictSnippets[strTitle].get("description", None)
    if strDescription:

        strFunctionDescrption = Regex.find_one(
            strObj=strDescription, pattern=r"^(.*?)(?=(Parameters:)|(Returns:))", dotAll=True
        )
        if not strFunctionDescrption:
            strAPI += strDescription + "\n\n"
            print("continue, repr:", repr(strDescription))
            continue
        strAPI += strFunctionDescrption + "\n\n"
        strParameters = Regex.find_one(
            strObj=strDescription, pattern=r"(?<=Parameters:\n)(.*?)(?=(Returns:)|$)", dotAll=True
        )
        if strParameters:
            strParameters = Regex.replace(strObj=strParameters, pattern="^    ", newStr="", multiLine=True)
            strParameters = strParameters.strip()
            strAPI += f"Parameters:\n\n```\n{strParameters}\n```\n\n"
        else:
            # print("Have no Parameters.")
            pass

        strReturns = Regex.find_one(strObj=strDescription, pattern=r"(?<=Returns:\n    ).*?(?=$)", dotAll=True)
        if strReturns:
            strAPI += f"Returns:\n\n```\n{strReturns}\n```\n\n"
    else:
        strAPI += "No need for description." + "\n\n"

Path("./snippets/api.md").write_text(strAPI)
