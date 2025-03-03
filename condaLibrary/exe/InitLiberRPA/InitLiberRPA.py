# FileName: InitLiberRPA.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


import os
from pathlib import Path
import shutil
import subprocess
import re
import json
import winreg

print(f"The current work folder: {os.getcwd()}")
strCwd = os.getcwd()


def set_liberrpa_environment() -> None:
    print("--set_liberrpa_environment--")
    strLiberRPAPath = os.environ.get("LiberRPA")
    if strLiberRPAPath:
        print(
            f"The current LiberRPA path has be added into User Environment variables is '{strLiberRPAPath}',do you want to replace it into '{strCwd}'?"
        )
        strUserInput = input("(y/other)").strip().lower()
        if strUserInput == "y":
            subprocess.run(["setx", "LiberRPA", strCwd])
            print(
                f"You pressed '{strUserInput}'. The LiberRPA path has be added into User Environment variables '{strCwd}'"
            )
            set_vscode_python_interpreter()
            create_native_messagin_file()
            install_font_for_current_user()
            set_LiberRPALocalServer_startup()
            put_shortcuts_to_desktop()
        else:
            print(f"You pressed '{strUserInput}'. Do nothing.")

    else:
        subprocess.run(["setx", "LiberRPA", strCwd])
        print(f"The LiberRPA path has be added into User Environment variables '{strCwd}'")
        set_vscode_python_interpreter()
        create_native_messagin_file()
        install_font_for_current_user()
        set_LiberRPALocalServer_startup()
        put_shortcuts_to_desktop()


def set_vscode_python_interpreter() -> None:
    print("--set_vscode_python_interpreter--")
    strPythonInterpreterPath = os.path.join(strCwd, R"envs\pyenv\python.exe")
    strSettingFilePath = os.path.join(strCwd, R"Editor\vscode\data\user-data\User\settings.json")
    print(f"The vscode setting.json's path is '{strSettingFilePath}'")

    strOriginal = Path(strSettingFilePath).read_text()
    match = re.search('"python.defaultInterpreterPath": ".*?exe"', strOriginal)
    if match:
        strFound = match.group()
        print(
            f"Update 'python.defaultInterpreterPath' from \n'{strFound}'\nto\n'\"python.defaultInterpreterPath\": {json.dumps(strPythonInterpreterPath)}'."
        )
        strNew = strOriginal.replace(
            strFound, f'"python.defaultInterpreterPath": {json.dumps(strPythonInterpreterPath)}'
        )
        Path(strSettingFilePath).write_text(data=strNew)
    else:
        print("Error: Have no key 'python.defaultInterpreterPath' in the setting.json!")


def create_folder_in_documents() -> None:
    print("--create_folder_in_documents--")
    strPath = os.path.join(os.environ.get("USERPROFILE", "N/A"), "Documents\\LiberRPA")

    if os.path.exists(strPath) == False:
        print(f"Create LiberRPA folder in User Documents: '{strPath}'")
        os.mkdir(strPath)


def create_native_messagin_file() -> None:
    print("--create_native_messagin_file--")
    # Create json file.
    strNmFolderPath = os.path.join(os.environ.get("USERPROFILE", "N/A"), "Documents\\LiberRPA\\NativeMessaging")
    strNmFilePath = os.path.join(strNmFolderPath, "liberrpachromemessage.json")
    if os.path.exists(strNmFolderPath) == False:
        print(f"Create Native Messaging folder: '{strNmFolderPath}'")
        os.mkdir(strNmFolderPath)
    strExePath = os.path.join(strCwd, R"exeFiles\ChromeGetLocalServerPort\ChromeGetLocalServerPort.exe")
    dictNM = {
        "name": "com.liberrpa.chrome.msghost",
        "description": "Chrome call native app and sent message to app.",
        "path": strExePath,
        "type": "stdio",
        "allowed_origins": ["chrome-extension://elnnnehambeohefmcdeiajpodhcdgigb/"],
    }
    Path(strNmFilePath).write_text(json.dumps(dictNM, indent=4), encoding="utf-8")

    # Add json file path into regedit.
    try:
        key = winreg.CreateKey(
            winreg.HKEY_CURRENT_USER, R"SOFTWARE\Google\Chrome\NativeMessagingHosts\com.liberrpa.chrome.msghost"
        )
        # Set the value
        winreg.SetValueEx(key, None, 0, winreg.REG_SZ, strNmFilePath)
        winreg.CloseKey(key)
        print("Add Native Messaging path to regedit successfully.")
    except Exception as e:
        print(f"Failed to add Native Messaging path to regedit: {e}")


def install_font_for_current_user() -> None:
    print("--install_font_for_current_user--")
    strLocalAppData = os.getenv("LOCALAPPDATA")

    strFontFilePath = os.path.join(strCwd, R"envs\assets\font\Noto_Sans_Mono\NotoSansMono-VariableFont_wdth,wght.ttf")

    if strLocalAppData:
        strTargetPath = (
            Path(strLocalAppData) / "Microsoft" / "Windows" / "Fonts" / "NotoSansMono-VariableFont_wdth,wght.ttf"
        )
        if Path(strTargetPath).is_file():
            print("The font 'Noto Sans Mono' has installed.")
        else:
            strPath = shutil.copy2(strFontFilePath, strTargetPath)
            print(f"Installed the font 'Noto Sans Mono' in {strPath}")


def set_LiberRPALocalServer_startup() -> None:
    print("--set_LiberRPALocalServer_startup--")
    pathShortcut = Path(strCwd) / "envs/assets/shortcut/LiberRPALocalServer.lnk"
    pathTarget = (
        Path(os.environ.get("USERPROFILE", "N/A")) / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup"
    )
    shutil.copy(src=pathShortcut, dst=pathTarget)


def put_shortcuts_to_desktop() -> None:
    print("--put_shortcuts_to_desktop--")
    for fileName in ["LiberRPALocalServer", "LiberRPA_UI_Analyzer", "LiberRPAEditor"]:
        pathShortcut = Path(strCwd) / f"envs/assets/shortcut/{fileName}.lnk"
        pathTarget = Path(os.environ.get("USERPROFILE", "N/A")) / "Desktop/"
        shutil.copy(src=pathShortcut, dst=pathTarget)


if __name__ == "__main__":
    try:
        create_folder_in_documents()
        set_liberrpa_environment()
    except Exception as e:
        print(e)
    finally:
        input("Press any key to exit...")
