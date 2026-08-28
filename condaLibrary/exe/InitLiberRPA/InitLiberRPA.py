# FileName: InitLiberRPA.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


import ctypes
from dataclasses import dataclass
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
from typing import Any
import winreg
from win32com.client import Dispatch


pathCwd = Path.cwd().resolve()
print(
    f"The current work folder: {pathCwd}, LiberRPA will be initialized according to the current path."
)
pathUser = Path.home()

_STEP_NAMES = (
    "create_liberrpa_folder_in_documents",
    "set_liberrpa_environment",
    "create_native_messaging_file",
    "create_local_auth",
    "install_font_for_current_user",
    "set_startup",
    "put_shortcuts_to_desktop",
    "check_Executor_config",
    "create_component_repository_folder",
)
_STEP_NAME_WIDTH = max(len(name) for name in _STEP_NAMES)

_ANSI_RESET = "\033[0m"
_ANSI_DIM = "\033[2m"
_ANSI_BOLD_CYAN = "\033[1;36m"
_ANSI_BOLD_GREEN = "\033[1;32m"


def _enable_ansi_color() -> bool:
    """Enable ANSI colors for the current console when supported."""
    if not sys.stdout.isatty():
        return False

    if os.name != "nt":
        return True

    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.GetStdHandle.argtypes = [ctypes.c_ulong]
        kernel32.GetStdHandle.restype = ctypes.c_void_p
        kernel32.GetConsoleMode.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint32),
        ]
        kernel32.SetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.c_uint32]

        stdOutputHandle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        invalidHandle = ctypes.c_void_p(-1).value
        if stdOutputHandle in (None, invalidHandle):
            return False

        currentMode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(stdOutputHandle, ctypes.byref(currentMode)):
            return False

        enableVirtualTerminalProcessing = 0x0004
        return bool(
            kernel32.SetConsoleMode(
                stdOutputHandle,
                currentMode.value | enableVirtualTerminalProcessing,
            )
        )
    except Exception:
        return False


_COLOR_ENABLED = _enable_ansi_color()


def _color_text(text: str, style: str) -> str:
    if not _COLOR_ENABLED:
        return text
    return f"{style}{text}{_ANSI_RESET}"


intCount = 0
_dictStepNumberByName: dict[str, int] = {}


def _format_step_line(stepNumber: int, name: str, status: str) -> str:
    strPrefix = f"[STEP {stepNumber:02d}]"
    strName = f"{name:<{_STEP_NAME_WIDTH}}"
    strStatus = f"[{status:<5}]"

    strStatusStyle = _ANSI_BOLD_GREEN if status == "DONE" else _ANSI_BOLD_CYAN
    return " ".join([
        _color_text(strPrefix, _ANSI_DIM),
        _color_text(strName, strStatusStyle),
        _color_text(strStatus, strStatusStyle),
    ])


def print_step(name: str) -> None:
    global intCount

    intCount += 1
    _dictStepNumberByName[name] = intCount

    print()
    print(_format_step_line(stepNumber=intCount, name=name, status="START"))


def print_step_done(name: str) -> None:
    intStepNumber = _dictStepNumberByName.pop(name, None)
    if intStepNumber is None:
        raise RuntimeError(f"Cannot finish an unknown initialization step: {name}")

    print(_format_step_line(stepNumber=intStepNumber, name=name, status="DONE"))
    print()


@dataclass(frozen=True)
class ShortcutSpec:
    fileName: str
    targetPath: Path
    workingDirectory: Path
    arguments: str = ""
    iconLocation: str = ""
    description: str = ""
    required: bool = True


def _get_shortcut_specs() -> dict[str, ShortcutSpec]:
    pathLocalServerIcon = (
        pathCwd / "envs" / "assets" / "icon" / "LiberRPA_icon_v3_color_LocalServer.ico"
    )

    return {
        "Editor-LiberRPA": ShortcutSpec(
            fileName="Editor-LiberRPA",
            targetPath=pathCwd / "Editor" / "Code.exe",
            workingDirectory=pathCwd / "Editor",
            description="Open LiberRPA Editor.",
        ),
        "Executor-LiberRPA": ShortcutSpec(
            fileName="Executor-LiberRPA",
            targetPath=pathCwd / "Executor" / "Executor.exe",
            workingDirectory=pathCwd / "Executor",
            description="Open LiberRPA Executor.",
            # Executor may be absent from a temporary pre-Executor RC build.
            required=False,
        ),
        "LocalServer-LiberRPA": ShortcutSpec(
            fileName="LocalServer-LiberRPA",
            targetPath=pathCwd / "envs" / "pyenv" / "default" / "pythonw.exe",
            workingDirectory=pathCwd / "exeFiles" / "LiberRPALocalServer",
            arguments="-m liberrpa.LiberRPALocalServer.LiberRPALocalServer",
            iconLocation=f"{pathLocalServerIcon},0",
            description="Start LiberRPA Local Server.",
        ),
        "UI_Analyzer-LiberRPA": ShortcutSpec(
            fileName="UI_Analyzer-LiberRPA",
            targetPath=pathCwd / "exeFiles" / "ui-analyzer" / "UI Analyzer.exe",
            workingDirectory=pathCwd / "exeFiles" / "ui-analyzer",
            description="Open LiberRPA UI Analyzer.",
        ),
    }


def _get_special_folder(wshShell: Any, name: str) -> Path:
    pathFolder = Path(str(wshShell.SpecialFolders(name))).resolve()
    if not pathFolder.is_dir():
        raise FileNotFoundError(f"Windows special folder does not exist: {pathFolder}")
    return pathFolder


def _get_icon_file_path(iconLocation: str) -> Path | None:
    if not iconLocation:
        return None

    strIconPath = iconLocation.rsplit(",", maxsplit=1)[0].strip()
    if not strIconPath:
        return None

    return Path(strIconPath)


def _create_shortcut(
    wshShell: Any,
    shortcutFolder: Path,
    shortcutSpec: ShortcutSpec,
) -> None:
    pathShortcut = shortcutFolder / f"{shortcutSpec.fileName}.lnk"

    if not shortcutSpec.targetPath.is_file():
        pathShortcut.unlink(missing_ok=True)
        strMessage = (
            f"Cannot create '{shortcutSpec.fileName}' because its target does not exist: "
            f"'{shortcutSpec.targetPath}'"
        )
        if shortcutSpec.required:
            raise FileNotFoundError(strMessage)

        print(f"[Warning] {strMessage}. Skip this shortcut.")
        return

    if not shortcutSpec.workingDirectory.is_dir():
        raise FileNotFoundError(
            f"Cannot create '{shortcutSpec.fileName}' because its working directory "
            f"does not exist: '{shortcutSpec.workingDirectory}'"
        )

    pathIcon = _get_icon_file_path(shortcutSpec.iconLocation)
    if pathIcon is not None and not pathIcon.is_file():
        raise FileNotFoundError(
            f"Cannot create '{shortcutSpec.fileName}' because its icon does not "
            f"exist: '{pathIcon}'"
        )

    shortcutFolder.mkdir(parents=True, exist_ok=True)
    pathShortcut.unlink(missing_ok=True)

    shortcutObj = wshShell.CreateShortcut(str(pathShortcut))
    shortcutObj.TargetPath = str(shortcutSpec.targetPath)
    shortcutObj.Arguments = shortcutSpec.arguments
    shortcutObj.WorkingDirectory = str(shortcutSpec.workingDirectory)
    shortcutObj.Description = shortcutSpec.description
    shortcutObj.WindowStyle = 1

    if shortcutSpec.iconLocation:
        shortcutObj.IconLocation = shortcutSpec.iconLocation

    shortcutObj.Save()

    # WScript.Shell may not report invalid shortcut parameters when saving.
    # Re-open the shortcut and verify the target written on this computer.
    shortcutCheckObj = wshShell.CreateShortcut(str(pathShortcut))
    pathCreatedTarget = Path(str(shortcutCheckObj.TargetPath)).resolve()
    if pathCreatedTarget != shortcutSpec.targetPath.resolve():
        raise RuntimeError(
            f"Shortcut target verification failed for '{pathShortcut}'. "
            f"Expected '{shortcutSpec.targetPath}', got '{pathCreatedTarget}'."
        )

    print(f"Create shortcut: '{pathShortcut}' -> '{shortcutSpec.targetPath}'")


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

    wshShell = Dispatch("WScript.Shell")
    pathStartup = _get_special_folder(wshShell=wshShell, name="Startup")
    dictShortcutSpec = _get_shortcut_specs()

    for strShortcutName in ["LocalServer-LiberRPA", "Executor-LiberRPA"]:
        _create_shortcut(
            wshShell=wshShell,
            shortcutFolder=pathStartup,
            shortcutSpec=dictShortcutSpec[strShortcutName],
        )

    print_step_done(name="set_startup")


def put_shortcuts_to_desktop() -> None:
    print_step(name="put_shortcuts_to_desktop")

    wshShell = Dispatch("WScript.Shell")
    pathDesktop = _get_special_folder(wshShell=wshShell, name="Desktop")
    dictShortcutSpec = _get_shortcut_specs()

    for strShortcutName in [
        "LocalServer-LiberRPA",
        "UI_Analyzer-LiberRPA",
        "Editor-LiberRPA",
        "Executor-LiberRPA",
    ]:
        _create_shortcut(
            wshShell=wshShell,
            shortcutFolder=pathDesktop,
            shortcutSpec=dictShortcutSpec[strShortcutName],
        )

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
