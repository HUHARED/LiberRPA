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
from typing import TypedDict, Literal, cast

type BasicConfigToolName = Literal["BuiltInTools", "Editor", "Executor"]


class DictBasicConfig(TypedDict):
    outputLogPath: str
    localServerPort: int
    uiAnalyzerTheme: Literal["light", "dark"]
    uiAnalyzerMinimizeWindow: bool
    componentRepositoryPath: str


class DictAuth(TypedDict):
    python: str
    uiAnalyzer: str
    chrome: str


def _read_basic_config_dict() -> DictBasicConfig:
    value = json5.loads(
        Path(get_liberrpa_folder_path())
        .joinpath("configFiles/basic.jsonc")
        .read_text(encoding="utf-8", errors="strict")
    )

    if (
        isinstance(value, dict)
        and set(value)
        == {
            "outputLogPath",
            "localServerPort",
            "uiAnalyzerTheme",
            "uiAnalyzerMinimizeWindow",
            "componentRepositoryPath",
        }
        and isinstance(value.get("outputLogPath"), str)
        and bool(value["outputLogPath"].strip())
        and isinstance(value.get("localServerPort"), int)
        and not isinstance(value.get("localServerPort"), bool)
        and 1 <= value["localServerPort"] <= 65535
        and value.get("uiAnalyzerTheme") in ("light", "dark")
        and isinstance(value.get("uiAnalyzerMinimizeWindow"), bool)
        and isinstance(value.get("componentRepositoryPath"), str)
        and bool(value["componentRepositoryPath"].strip())
    ):
        return cast(DictBasicConfig, value)

    raise ValueError(
        "Invalid 'basic.jsonc'. Expected keys: "
        "outputLogPath(non-empty str), localServerPort(int 1-65535), "
        "uiAnalyzerTheme('light'|'dark'), uiAnalyzerMinimizeWindow(bool), "
        "componentRepositoryPath(non-empty str)."
    )


def get_basic_config_dict(toolName: BasicConfigToolName) -> DictBasicConfig:

    dictReplaceKeywords: dict[str, str] = {
        "${LiberRPA}": get_liberrpa_folder_path(),
        "${UserName}": getpass.getuser(),
        "${HostName}": socket.gethostname(),
        "${ToolName}": toolName,
    }

    # Open the json file to get original dict.
    dictBasicConfig = _read_basic_config_dict()

    # Replace predefined variables.
    for strKeyOuter in dictBasicConfig:
        if isinstance(dictBasicConfig[strKeyOuter], str):
            for strKeyInner, strReplacement in dictReplaceKeywords.items():
                dictBasicConfig[strKeyOuter] = dictBasicConfig[strKeyOuter].replace(
                    strKeyInner,
                    strReplacement,
                )

    return dictBasicConfig


def get_local_server_port() -> int:
    return _read_basic_config_dict()["localServerPort"]


def get_token(clientType: Literal["python", "chrome", "uiAnalyzer"]) -> str:

    pathAuthFile = Path.home() / R"Documents\LiberRPA\WebSocketAuth.json"

    if not pathAuthFile.is_file():
        raise FileNotFoundError(
            "WebSocketAuth.json was not found. Please run InitLiberRPA.exe to initialize or update LiberRPA."
        )

    value = json5.loads(pathAuthFile.read_text(encoding="utf-8"))

    if (
        isinstance(value, dict)
        and set(value) == {"python", "uiAnalyzer", "chrome"}
        and isinstance(value.get("python"), str)
        and isinstance(value.get("uiAnalyzer"), str)
        and isinstance(value.get("chrome"), str)
    ):
        return value[clientType]
    else:
        raise ValueError("Invalid 'WebSocketAuth.json'. Expected keys: python(str), uiAnalyzer(str), chrome(str).")


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
    ...
