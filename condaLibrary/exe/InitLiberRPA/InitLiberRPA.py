# FileName: InitLiberRPA.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


import os
from pathlib import Path
import shutil
import subprocess
import json
import winreg
import secrets

pathCwd = Path.cwd().resolve()
print(
    f"The current work folder: {pathCwd}, LiberRPA will be initialized according to the current path."
)
pathUser = Path.home()


intCount = 0


def print_step(name: str) -> None:
    global intCount
    intCount += 1
    print(f"##### Step {intCount}: {name} #####")


def print_step_done(name: str) -> None:
    print(f"##### Step {name} completed #####\n")


def create_liberrpa_folder_in_documents() -> None:
    print_step(name="create_liberrpa_folder_in_documents")

    pathObj = pathUser / "Documents" / "LiberRPA"

    if not pathObj.is_dir():
        print(f"Create LiberRPA folder in User Documents: '{pathObj}'")
        pathObj.mkdir(parents=True, exist_ok=False)
    else:
        print("LiberRPA folder in User Documents has existed.")

    print_step_done(name="create_liberrpa_folder_in_documents")


def _set_user_environment_variable(name: str, value: str) -> None:
    """Set a persistent user environment variable and update this process immediately."""
    subprocess.run(["setx", name, value], check=True)
    os.environ[name] = value
    print(
        "[Note] Please restart LiberRPA Editor after initialization so it can read the updated environment variable."
    )


def set_liberrpa_environment() -> None:
    print_step(name="set_liberrpa_environment")

    strLiberRPAPath = os.environ.get("LiberRPA")

    if strLiberRPAPath:
        print(
            f"The current LiberRPA user environment variable is '{strLiberRPAPath}'.\n"
            f"Do you want to replace it with '{pathCwd}'?\n"
            "Choose 'y' when installing or updating LiberRPA, even if the folder path is unchanged. "
            "This refreshes local config files and WebSocket auth tokens, so related local services should be restarted."
        )

        strUserInput = input("(y/other)").strip().lower()

        if strUserInput == "y":
            _set_user_environment_variable(name="LiberRPA", value=str(pathCwd))
            print(
                f"You pressed '{strUserInput}'. The LiberRPA user environment variable has been set to '{pathCwd}'."
            )

        else:
            print(f"You pressed '{strUserInput}'. Do nothing.")
            return None

    else:
        _set_user_environment_variable(name="LiberRPA", value=str(pathCwd))
        print(f"The LiberRPA user environment variable has been set to '{pathCwd}'.")

    print_step_done(name="set_liberrpa_environment")

    # Do other settings.
    create_native_messaging_file()
    create_local_auth()
    install_font_for_current_user()
    set_startup()
    put_shortcuts_to_desktop()
    check_Executor_config()
    create_component_repository_folder()


def create_native_messaging_file() -> None:
    print_step(name="create_native_messaging_file")

    # Create json file.
    pathNmFolder = pathUser / R"Documents\LiberRPA\NativeMessaging"
    pathNmFile = pathNmFolder / "liberrpachromemessage.json"
    if not pathNmFolder.is_dir():
        print(f"Create Native Messaging folder: '{pathNmFolder}'")
        pathNmFolder.mkdir(parents=True, exist_ok=True)
    pathExe = pathCwd / R"exeFiles\ChromeGetLocalServerPort\ChromeGetLocalServerPort.exe"
    dictNM = {
        "name": "com.liberrpa.chrome.msghost",
        "description": "Allows the LiberRPA Chrome extension to call the local native app.",
        "path": str(pathExe),
        "type": "stdio",
        "allowed_origins": [
            "chrome-extension://cffobgimbemkfgjmcedebofkfcamnajb/",  # Web Store version
            "chrome-extension://elnnnehambeohefmcdeiajpodhcdgigb/",  # Developing
        ],
    }
    Path(pathNmFile).write_text(json.dumps(dictNM, indent=4), encoding="utf-8")

    # Add json file path into regedit.
    try:
        key = winreg.CreateKey(
            winreg.HKEY_CURRENT_USER,
            R"SOFTWARE\Google\Chrome\NativeMessagingHosts\com.liberrpa.chrome.msghost",
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
            pathFontFile = (
                pathCwd
                / R"envs\assets\font\Noto_Sans_Mono\NotoSansMono-VariableFont_wdth,wght.ttf"
            )

            strPath = shutil.copy2(pathFontFile, pathTarget)
            print(f"Installed the font 'Noto Sans Mono' in {strPath}")
    else:
        print(f"[Error] Not found LOCALAPPDATA: {pathLocalAppData}")

    print_step_done(name="install_font_for_current_user")


def set_startup() -> None:
    print_step(name="set_startup")

    for fileName in ["LocalServer-LiberRPA", "Executor-LiberRPA"]:
        pathShortcut = pathCwd / f"envs/assets/shortcut/{fileName}.lnk"
        pathTarget = (
            pathUser / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup"
        )
        shutil.copy(src=pathShortcut, dst=pathTarget)
        print(f"Add {fileName} into {pathTarget}")

    print_step_done(name="set_startup")


def put_shortcuts_to_desktop() -> None:

    print_step(name="put_shortcuts_to_desktop")

    for fileName in [
        "LocalServer-LiberRPA",
        "UI_Analyzer-LiberRPA",
        "Editor-LiberRPA",
        "Executor-LiberRPA",
    ]:
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
            "[Note] Please check the Executor settings and make sure they suit your needs. "
            "(Especially if the current LiberRPA folder was copied from another computer.)"
        )
    else:
        print("Executor will be initialized when user first open it.")

    print_step_done(name="check_Executor_config")


def create_local_auth() -> None:
    print_step(name="create_local_auth")

    pathAuthFile = pathUser / R"Documents\LiberRPA\WebSocketAuth.json"

    # Generate independent tokens for different client types.
    dictAuth = {
        "python": secrets.token_urlsafe(32),
        "uiAnalyzer": secrets.token_urlsafe(32),
        "chrome": secrets.token_urlsafe(32),
    }

    Path(pathAuthFile).write_text(json.dumps(dictAuth, indent=4), encoding="utf-8")
    print("WebSocket auth file has been created.")
    print_step_done(name="create_local_auth")


def create_component_repository_folder() -> None:
    print_step(name="create_component_repository_folder")

    pathComponentRepository = pathUser / R"Documents\LiberRPA\ComponentRepository"

    if pathComponentRepository.is_dir():
        print("ComponentRepository folder has existed.")
    else:
        pathComponentRepository.mkdir(parents=True, exist_ok=False)
        print(f"Create ComponentRepository folder: '{pathComponentRepository}'")

    print_step_done(name="create_component_repository_folder")


if __name__ == "__main__":
    try:
        create_liberrpa_folder_in_documents()
        set_liberrpa_environment()
    except Exception as e:
        print(f"[Error] {e}")
        raise SystemExit(1) from e
    finally:
        input("Press any key to exit...")
