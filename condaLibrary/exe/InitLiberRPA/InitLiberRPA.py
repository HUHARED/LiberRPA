# FileName: InitLiberRPA.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


import argparse
import ctypes
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import winreg

from _Editor import prepare_editor as _prepare_editor_files
from _EditorExtensions import install_editor_extensions as _install_editor_extensions
from _Shortcut import create_desktop_shortcuts, create_startup_shortcuts


_STEP_NAMES = (
    "create_liberrpa_folder_in_documents",
    "set_liberrpa_environment",
    "prepare_editor",
    "create_native_messaging_file",
    "create_local_auth",
    "install_font_for_current_user",
    "install_editor_extensions",
    "set_startup",
    "put_shortcuts_to_desktop",
    "check_executor_config",
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
_intStepCount = 0
_dictStepNumberByName: dict[str, int] = {}


def _color_text(text: str, style: str) -> str:
    if not _COLOR_ENABLED:
        return text
    return f"{style}{text}{_ANSI_RESET}"


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
    global _intStepCount

    _intStepCount += 1
    _dictStepNumberByName[name] = _intStepCount

    print()
    print(_format_step_line(stepNumber=_intStepCount, name=name, status="START"))


def print_step_done(name: str) -> None:
    intStepNumber = _dictStepNumberByName.pop(name, None)
    if intStepNumber is None:
        raise RuntimeError(f"Cannot finish an unknown initialization step: {name}")

    print(_format_step_line(stepNumber=intStepNumber, name=name, status="DONE"))
    print()


def create_liberrpa_folder_in_documents(userPath: Path) -> None:
    print_step(name="create_liberrpa_folder_in_documents")

    pathObj = userPath / "Documents" / "LiberRPA"

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


def set_liberrpa_environment(rootPath: Path) -> bool:
    print_step(name="set_liberrpa_environment")

    strLiberRPAPath = os.environ.get("LiberRPA")

    if strLiberRPAPath:
        print(
            f"The current LiberRPA user environment variable is '{strLiberRPAPath}'.\n"
            f"Do you want to replace it with '{rootPath}'?\n"
            "Choose 'y' when installing or updating LiberRPA, even if the folder path is unchanged. "
            "This refreshes local config files and WebSocket auth tokens, so related local "
            "services should be restarted."
        )

        strUserInput = input("(y/other)").strip().lower()

        if strUserInput != "y":
            print(f"You pressed '{strUserInput}'. Do nothing.")
            print_step_done(name="set_liberrpa_environment")
            return False

        _set_user_environment_variable(name="LiberRPA", value=str(rootPath))
        print(
            f"You pressed '{strUserInput}'. The LiberRPA user environment variable has been set to '{rootPath}'."
        )
    else:
        _set_user_environment_variable(name="LiberRPA", value=str(rootPath))
        print(f"The LiberRPA user environment variable has been set to '{rootPath}'.")

    print_step_done(name="set_liberrpa_environment")
    return True


def prepare_editor(rootPath: Path) -> None:
    print_step(name="prepare_editor")
    _prepare_editor_files(rootPath=rootPath)
    print_step_done(name="prepare_editor")


def create_native_messaging_file(rootPath: Path, userPath: Path) -> None:
    print_step(name="create_native_messaging_file")

    pathNmFolder = userPath / R"Documents\LiberRPA\NativeMessaging"
    pathNmFile = pathNmFolder / "liberrpachromemessage.json"
    if not pathNmFolder.is_dir():
        print(f"Create Native Messaging folder: '{pathNmFolder}'")
        pathNmFolder.mkdir(parents=True, exist_ok=True)

    pathExe = rootPath / R"exeFiles\ChromeGetLocalServerPort\ChromeGetLocalServerPort.exe"
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
    pathNmFile.write_text(json.dumps(dictNM, indent=4), encoding="utf-8")

    try:
        key = winreg.CreateKey(
            winreg.HKEY_CURRENT_USER,
            R"SOFTWARE\Google\Chrome\NativeMessagingHosts\com.liberrpa.chrome.msghost",
        )
        winreg.SetValueEx(key, None, 0, winreg.REG_SZ, str(pathNmFile))
        winreg.CloseKey(key)
        print(
            "Add Native Messaging path to regedit successfully. "
            R"(HKEY_CURRENT_USER\SOFTWARE\Google\Chrome\NativeMessagingHosts\com.liberrpa.chrome.msghost)"
        )
    except Exception as e:
        print(f"[Error] Failed to add Native Messaging path to regedit: {e}")

    print_step_done(name="create_native_messaging_file")


def create_local_auth(userPath: Path) -> None:
    print_step(name="create_local_auth")

    pathAuthFile = userPath / R"Documents\LiberRPA\WebSocketAuth.json"

    dictAuth = {
        "python": secrets.token_urlsafe(32),
        "uiAnalyzer": secrets.token_urlsafe(32),
        "chrome": secrets.token_urlsafe(32),
    }

    pathAuthFile.write_text(json.dumps(dictAuth, indent=4), encoding="utf-8")
    print("WebSocket auth file has been created.")
    print_step_done(name="create_local_auth")


def install_font_for_current_user(rootPath: Path, userPath: Path) -> None:
    print_step(name="install_font_for_current_user")

    pathLocalAppData = userPath / "AppData" / "Local"

    if pathLocalAppData.is_dir():
        pathUserFontsFolder = pathLocalAppData / "Microsoft" / "Windows" / "Fonts"
        pathUserFontsFolder.mkdir(parents=True, exist_ok=True)

        pathTarget = pathUserFontsFolder / "NotoSansMono-VariableFont_wdth,wght.ttf"

        if pathTarget.is_file():
            print("The font 'Noto Sans Mono' has installed.")
        else:
            pathFontFile = (
                rootPath
                / R"envs\assets\font\Noto_Sans_Mono\NotoSansMono-VariableFont_wdth,wght.ttf"
            )

            strPath = shutil.copy2(pathFontFile, pathTarget)
            print(f"Installed the font 'Noto Sans Mono' in {strPath}")
    else:
        print(f"[Error] Not found LOCALAPPDATA: {pathLocalAppData}")

    print_step_done(name="install_font_for_current_user")


def install_editor_extensions(rootPath: Path) -> None:
    print_step(name="install_editor_extensions")
    _install_editor_extensions(rootPath=rootPath)
    print_step_done(name="install_editor_extensions")


def set_startup(rootPath: Path) -> None:
    print_step(name="set_startup")
    create_startup_shortcuts(rootPath=rootPath)
    print_step_done(name="set_startup")


def put_shortcuts_to_desktop(rootPath: Path) -> None:
    print_step(name="put_shortcuts_to_desktop")
    create_desktop_shortcuts(rootPath=rootPath)
    print_step_done(name="put_shortcuts_to_desktop")


def check_executor_config(rootPath: Path) -> None:
    print_step(name="check_executor_config")

    pathSettingFile = rootPath / R"configFiles\Executor.jsonc"
    if pathSettingFile.is_file():
        print(
            "[Note] Please check the Executor settings and make sure they suit your needs. "
            "(Especially if the current LiberRPA folder was copied from another computer.)"
        )
    else:
        print("Executor will be initialized when user first open it.")

    print_step_done(name="check_executor_config")


def create_component_repository_folder(userPath: Path) -> None:
    print_step(name="create_component_repository_folder")

    pathComponentRepository = userPath / R"Documents\LiberRPA\ComponentRepository"

    if pathComponentRepository.is_dir():
        print("ComponentRepository folder has existed.")
    else:
        pathComponentRepository.mkdir(parents=True, exist_ok=False)
        print(f"Create ComponentRepository folder: '{pathComponentRepository}'")

    print_step_done(name="create_component_repository_folder")


def initialize_liberrpa(rootPath: Path, userPath: Path) -> None:
    create_liberrpa_folder_in_documents(userPath=userPath)

    if not set_liberrpa_environment(rootPath=rootPath):
        return

    # Editor preparation must finish before using its CLI or creating Editor shortcuts.
    prepare_editor(rootPath=rootPath)
    create_native_messaging_file(rootPath=rootPath, userPath=userPath)
    create_local_auth(userPath=userPath)
    install_font_for_current_user(rootPath=rootPath, userPath=userPath)
    install_editor_extensions(rootPath=rootPath)
    set_startup(rootPath=rootPath)
    put_shortcuts_to_desktop(rootPath=rootPath)
    check_executor_config(rootPath=rootPath)
    create_component_repository_folder(userPath=userPath)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Initialize LiberRPA for the current Windows user."
    )
    parser.add_argument(
        "--editor-only",
        action="store_true",
        help="Prepare Editor in the current directory without changing user settings, tokens, or shortcuts.",
    )
    return parser.parse_args()


def main() -> None:
    rootPath = Path.cwd().resolve()
    userPath = Path.home()
    print(
        f"The current work folder: {rootPath}, LiberRPA will be initialized according to the current path."
    )

    args = _parse_args()
    try:
        if args.editor_only:
            prepare_editor(rootPath=rootPath)
        else:
            initialize_liberrpa(rootPath=rootPath, userPath=userPath)
    except KeyboardInterrupt:
        print("\n[Cancelled] Initialization was interrupted.")
        raise SystemExit(130) from None
    except Exception as e:
        print(f"[Error] {e}")
        raise SystemExit(1) from e
    finally:
        try:
            input("Press Enter to exit...")
        except (EOFError, KeyboardInterrupt):
            pass


if __name__ == "__main__":
    main()
