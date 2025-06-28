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


pathCwd = Path.cwd()
print(f"The current work folder: {pathCwd}, LiberRPA will be initialized according to the current path.")
pathUser = Path.home()


intCount = 0


def print_step(name: str) -> None:
    global intCount
    intCount += 1
    print(f"##### Step {intCount}: {name} #####")


def print_step_done(name: str) -> None:
    print(f"##### Step {name} completed #####\n")


def create_folder_in_documents() -> None:
    print_step(name="create_folder_in_documents")

    pathObj = pathUser / "Documents" / "LiberRPA"

    if pathObj.is_dir() == False:
        print(f"Create LiberRPA folder in User Documents: '{pathObj}'")
        pathObj.mkdir(parents=True, exist_ok=False)
    else:
        print("LiberRPA folder in User Documents has existed.")

    print_step_done(name="create_folder_in_documents")


def set_liberrpa_environment() -> None:
    print_step(name="set_liberrpa_environment")

    strLiberRPAPath = os.environ.get("LiberRPA")

    if strLiberRPAPath:
        print(
            f"The current LiberRPA path has be added into User Environment variables is '{strLiberRPAPath}',do you want to replace it into '{pathCwd}'?"
        )

        strUserInput = input("(y/other)").strip().lower()

        if strUserInput == "y":
            subprocess.run(["setx", "LiberRPA", str(pathCwd)])
            print(
                f"You pressed '{strUserInput}'. The LiberRPA path has be added into User Environment variables '{pathCwd}'"
            )
            # Make sure it works immediately.
            os.environ["LiberRPA"] = str(pathCwd)

        else:
            print(f"You pressed '{strUserInput}'. Do nothing.")
            return None

    else:
        subprocess.run(["setx", "LiberRPA", str(pathCwd)])
        print(f"The LiberRPA path has be added into User Environment variables '{pathCwd}'")

    print_step_done(name="set_liberrpa_environment")

    # Do other settings.
    set_vscode_python_interpreter()
    create_native_messaging_file()
    install_font_for_current_user()
    set_startup()
    put_shortcuts_to_desktop()
    check_Executor_config()


def set_vscode_python_interpreter() -> None:
    print_step(name="set_vscode_python_interpreter")

    pathSettingFile = pathCwd / R"Editor\data\user-data\User\settings.json"
    print(f"The vscode setting.json's path is '{pathSettingFile}'")

    strOriginal = pathSettingFile.read_text()
    match = re.search('"python.defaultInterpreterPath": ".*?exe"', strOriginal)
    if match:
        strFound = match.group()

        pathPythonInterpreter = pathCwd / R"envs\pyenv\python.exe"

        print(
            f"Update 'python.defaultInterpreterPath' from \n'{strFound}'\nto\n'\"python.defaultInterpreterPath\": {json.dumps(str(pathPythonInterpreter))}'."
        )
        strNew = strOriginal.replace(
            strFound, f'"python.defaultInterpreterPath": {json.dumps(str(pathPythonInterpreter))}'
        )
        pathSettingFile.write_text(data=strNew)
    else:
        print("[Error] Have no key 'python.defaultInterpreterPath' in the setting.json!")

    print_step_done(name="set_vscode_python_interpreter")


def create_native_messaging_file() -> None:
    print_step(name="create_native_messaging_file")

    # Create json file.
    pathNmFolder = pathUser / R"Documents\LiberRPA\NativeMessaging"
    pathNmFile = pathNmFolder / "liberrpachromemessage.json"
    if pathNmFolder.is_dir() == False:
        print(f"Create Native Messaging folder: '{pathNmFolder}'")
        pathNmFolder.mkdir(parents=True, exist_ok=True)
    pathExe = pathCwd / R"exeFiles\ChromeGetLocalServerPort\ChromeGetLocalServerPort.exe"
    dictNM = {
        "name": "com.liberrpa.chrome.msghost",
        "description": "Chrome call native app and sent message to app.",
        "path": str(pathExe),
        "type": "stdio",
        "allowed_origins": ["chrome-extension://cffobgimbemkfgjmcedebofkfcamnajb/"],
    }
    Path(pathNmFile).write_text(json.dumps(dictNM, indent=4), encoding="utf-8")

    # Add json file path into regedit.
    try:
        key = winreg.CreateKey(
            winreg.HKEY_CURRENT_USER, R"SOFTWARE\Google\Chrome\NativeMessagingHosts\com.liberrpa.chrome.msghost"
        )
        # Set the value
        winreg.SetValueEx(key, None, 0, winreg.REG_SZ, str(pathNmFile))
        winreg.CloseKey(key)
        print(
            R"Add Native Messaging path to regedit successfully. (HKEY_CURRENT_USER\SOFTWARE\Google\Chrome\NativeMessagingHosts\com.liberrpa.chrome.msghost)"
        )
    except Exception as e:
        print(f"[Error] Failed to add Native Messaging path to regedit: {e}")

    print_step_done(name="create_native_messaging_file")


def install_font_for_current_user() -> None:
    print_step(name="install_font_for_current_user")

    pathLocalAppData = pathUser / "AppData" / "Local"

    if pathLocalAppData.is_dir():
        # Create the folder if it doesn't exist.
        pathUserFontsFolder = pathLocalAppData / "Microsoft" / "Windows" / "Fonts"
        pathUserFontsFolder.mkdir(parents=True, exist_ok=True)

        pathTarget = pathUserFontsFolder / "NotoSansMono-VariableFont_wdth,wght.ttf"

        if pathTarget.is_file():
            print("The font 'Noto Sans Mono' has installed.")
        else:

            pathFontFile = pathCwd / R"envs\assets\font\Noto_Sans_Mono\NotoSansMono-VariableFont_wdth,wght.ttf"

            strPath = shutil.copy2(pathFontFile, pathTarget)
            print(f"Installed the font 'Noto Sans Mono' in {strPath}")
    else:
        print(f"[Error] Not found LOCALAPPDATA: {pathLocalAppData}")

    print_step_done(name="install_font_for_current_user")


def set_startup() -> None:
    print_step(name="set_startup")

    for fileName in ["LocalServer-LiberRPA", "Executor-LiberRPA"]:
        pathShortcut = pathCwd / f"envs/assets/shortcut/{fileName}.lnk"
        pathTarget = pathUser / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup"
        shutil.copy(src=pathShortcut, dst=pathTarget)
        print(f"Add {fileName} into {pathTarget}")

    print_step_done(name="set_startup")


def put_shortcuts_to_desktop() -> None:

    print_step(name="put_shortcuts_to_desktop")

    for fileName in ["LocalServer-LiberRPA", "UI_Analyzer-LiberRPA", "Editor-LiberRPA", "Executor-LiberRPA"]:
        pathShortcut = pathCwd / f"envs/assets/shortcut/{fileName}.lnk"
        pathTarget = pathUser / "Desktop/"
        shutil.copy(src=pathShortcut, dst=pathTarget)
        print(f"Add {fileName} into {pathTarget}")

    print_step_done(name="put_shortcuts_to_desktop")


def check_Executor_config() -> None:
    print_step(name="check_Executor_config")

    strSettingFilePath = pathCwd / R"configFiles\Executor.jsonc"
    if Path(strSettingFilePath).is_file():
        print(
            f"[Note] Please check Executor's setting, make sure it suit your needs. (Especially if the current LiberRPA folder is copied from another computer.)"
        )
    else:
        print("Executor will be initialized when user first open it.")

    print_step_done(name="check_Executor_config")


if __name__ == "__main__":
    try:
        create_folder_in_documents()
        set_liberrpa_environment()
    except Exception as e:
        print(f"[Error] {e}")
    finally:
        input("Press any key to exit...")
