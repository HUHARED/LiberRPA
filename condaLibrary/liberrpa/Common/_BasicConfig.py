# FileName: _BasicConfig.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


import os
import getpass
from pathlib import Path
import socket
import json5
from typing import TypedDict, Literal, Any, cast
from liberrpa.Common._Utils import PATH_PROJECT_JSON


class DictBasicConfig(TypedDict):
    outputLogPath: str
    localServerPort: int
    uiAnalyzerTheme: Literal["light", "dark"]
    uiAnalyzerMinimizeWindow: bool


class DictAuth(TypedDict):
    python: str
    uiAnalyzer: str
    chrome: str


def _read_basic_config_dict() -> DictBasicConfig:
    return cast(
        DictBasicConfig,
        json5.loads(
            Path(get_liberrpa_folder_path())
            .joinpath("configFiles/basic.jsonc")
            .read_text(encoding="utf-8", errors="strict")
        ),
    )


def get_basic_config_dict() -> DictBasicConfig:

    dictReplaceKeywords: dict[str, str] = {
        "${LiberRPA}": get_liberrpa_folder_path(),
        "${UserName}": getpass.getuser(),
        "${HostName}": socket.gethostname(),
    }

    if os.getenv("LogFolderName") in ["_LiberRPALocalServer"]:
        dictReplaceKeywords["${ToolName}"] = "BuiltInTools"
    else:
        dictProject = cast(dict[str, Any], json5.loads(PATH_PROJECT_JSON.read_text(encoding="utf-8")))

        if dictProject.get("executorPackage"):
            dictReplaceKeywords["${ToolName}"] = "Executor"

        else:
            # Suppose other Python programs are running in vscode.
            dictReplaceKeywords["${ToolName}"] = "Editor"

    # Open the json file to get original dict.
    dictBasicConfig = _read_basic_config_dict()

    # Replace predefined variables
    for strKeyOuter in dictBasicConfig:
        if isinstance(dictBasicConfig[strKeyOuter], str):
            for strKeyInner in dictReplaceKeywords:
                dictBasicConfig[strKeyOuter] = dictBasicConfig[strKeyOuter].replace(
                    strKeyInner, dictReplaceKeywords[strKeyInner]
                )
    return dictBasicConfig


def get_local_server_port() -> int:

    dictBasicConfig = _read_basic_config_dict()

    try:
        port = dictBasicConfig["localServerPort"]

    except KeyError:
        raise KeyError(
            "'localServerPort' was not found in basic.jsonc.\nPlease run InitLiberRPA.exe to initialize LiberRPA."
        )

    if not isinstance(port, int):
        raise TypeError("'localServerPort' in basic.jsonc must be an integer.")

    if not 1 <= port <= 65535:
        raise ValueError("'localServerPort' in basic.jsonc must be between 1 and 65535.")

    return port


def get_token(clientType: Literal["python", "chrome", "uiAnalyzer"]) -> str:

    pathAuthFile = Path.home() / R"Documents\LiberRPA\WebSocketAuth.json"

    if not pathAuthFile.is_file():
        raise FileNotFoundError(
            "WebSocketAuth.json was not found. Please run InitLiberRPA.exe to initialize or update LiberRPA."
        )

    dictAuth: DictAuth = cast(DictAuth, json5.loads(pathAuthFile.read_text(encoding="utf-8")))
    try:
        return dictAuth[clientType]
    except KeyError:
        raise KeyError(
            f"Token for client type {clientType!r} was not found in WebSocketAuth.json.\nPlease run InitLiberRPA.exe to refresh local WebSocket auth tokens."
        )


def get_liberrpa_folder_path() -> str:
    strPath = os.environ.get("LiberRPA")
    if strPath:
        return strPath
    else:
        raise ValueError(
            'Didn\'t find LiberRPA in System Environment Variable. You should run the "InitLiberRPA.exe" in the LiberRPA root folder. It will add a "LiberRPA" variable in your computer\'s User Environment Variables.'
        )


def get_liberrpa_ico_path(
    component: Literal["LiberRPALocalServer", "LiberRPALocalServer_Indicating"] | None = None,
) -> str:
    strLiberRPAPath = get_liberrpa_folder_path()
    if component == "LiberRPALocalServer":
        strIconPath = Path(strLiberRPAPath) / "envs/assets/icon/LiberRPA_icon_v3_color_LocalServer.ico"
    elif component == "LiberRPALocalServer_Indicating":
        strIconPath = Path(strLiberRPAPath) / "envs/assets/icon/LiberRPA_icon_v3_color_LocalServer_indicating.ico"
    else:
        strIconPath = Path(strLiberRPAPath) / "envs/assets/icon/LiberRPA_icon_v3_color.ico"
    if not Path(strIconPath).is_file():
        raise FileNotFoundError("LiberRPA icon file is missing: " + str(strIconPath))
    # print("strIconPath=", strIconPath)
    return str(strIconPath)


if __name__ == "__main__":
    print(type(get_basic_config_dict()))
    print(get_basic_config_dict())
