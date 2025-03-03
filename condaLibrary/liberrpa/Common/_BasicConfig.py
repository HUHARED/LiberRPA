# FileName: _BasicConfig.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


import os
from pathlib import Path
import socket
import json5
from typing import Literal


def get_basic_config_dict() -> dict[str, str]:

    strConfigPath: str = get_liberrpa_folder_path()

    dictReplaceKeywords: dict[str, str] = {
        "${LiberRPA}": strConfigPath,
        "${UserName}": os.getlogin(),
        "${HostName}": socket.gethostname(),
    }

    if os.getenv("LogFolderName") in ["_ChromeGetLocalServerPort", "_LiberRPALocalServer"]:
        dictReplaceKeywords["${ToolName}"] = "BuildinTools"

    else:
        # Suppose other Python programs are running in vscode.
        # NOTE: If LiberRPA Executor was started development, add more logic to distinguish.
        dictReplaceKeywords["${ToolName}"] = "Editor"

    # Open the json file to get original dict.
    dictEditorConfig: dict[str, str] = json5.loads(
        Path(strConfigPath).joinpath("./configFiles/basic.jsonc").read_text(encoding="utf-8", errors="strict")
    )  # type: ignore - type is right

    # Replace predefined variables
    for strKeyOuter in dictEditorConfig:
        for strKeyInner in dictReplaceKeywords:
            dictEditorConfig[strKeyOuter] = dictEditorConfig[strKeyOuter].replace(
                strKeyInner, dictReplaceKeywords[strKeyInner]
            )
    return dictEditorConfig


def get_liberrpa_folder_path() -> str:
    strPath = os.environ.get("LiberRPA")
    if strPath:
        return strPath
    else:
        raise ValueError(
            f'Didn\'t find LiberRPA in System Environment Variable. You should run the "InitLiberRPA.exe" in the LiberRPA root folder. It will add a "LiberRPA" variable in your computer\'s User Environment Variables.'
        )


def get_liberrpa_ico_path(component: Literal["LiberRPALocalServer"] | None = None) -> str:
    strLiberRPAPath = get_liberrpa_folder_path()
    if component == "LiberRPALocalServer":
        strIconPath = Path(strLiberRPAPath) / "envs/assets/icon/LiberRPA_icon_v1_color_LocalServer.ico"
    else:
        strIconPath = Path(strLiberRPAPath) / "envs/assets/icon/LiberRPA_icon_v1_color.ico"
    if not Path(strIconPath).is_file():
        raise FileNotFoundError("LiberRPA icon file is missing: " + str(strIconPath))
    print("strIconPath=", strIconPath)
    return str(strIconPath)


if __name__ == "__main__":
    print(type(get_basic_config_dict()))
    print(get_basic_config_dict())
