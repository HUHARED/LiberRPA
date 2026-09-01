# FileName: _Shortcut.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from dataclasses import dataclass
from pathlib import Path
from typing import Any
from win32com.client import Dispatch


@dataclass(frozen=True)
class ShortcutSpec:
    fileName: str
    targetPath: Path
    workingDirectory: Path
    arguments: str = ""
    iconLocation: str = ""
    description: str = ""
    required: bool = True


def _get_shortcut_specs(rootPath: Path) -> dict[str, ShortcutSpec]:
    pathLocalServerIcon = (
        rootPath / "envs" / "assets" / "icon" / "LiberRPA_icon_v3_color_LocalServer.ico"
    )

    return {
        "Editor-LiberRPA": ShortcutSpec(
            fileName="Editor-LiberRPA",
            targetPath=rootPath / "Editor" / "Code.exe",
            workingDirectory=rootPath / "Editor",
            description="Open LiberRPA Editor.",
        ),
        "Executor-LiberRPA": ShortcutSpec(
            fileName="Executor-LiberRPA",
            targetPath=rootPath / "Executor" / "Executor.exe",
            workingDirectory=rootPath / "Executor",
            description="Open LiberRPA Executor.",
            # Executor may be absent from a temporary pre-Executor RC build.
            required=False,
        ),
        "LocalServer-LiberRPA": ShortcutSpec(
            fileName="LocalServer-LiberRPA",
            targetPath=rootPath / "envs" / "pyenv" / "default" / "pythonw.exe",
            workingDirectory=rootPath / "exeFiles" / "LiberRPALocalServer",
            arguments="-m liberrpa.LiberRPALocalServer.LiberRPALocalServer",
            iconLocation=f"{pathLocalServerIcon},0",
            description="Start LiberRPA Local Server.",
        ),
        "UI_Analyzer-LiberRPA": ShortcutSpec(
            fileName="UI_Analyzer-LiberRPA",
            targetPath=rootPath / "exeFiles" / "ui-analyzer" / "UI Analyzer.exe",
            workingDirectory=rootPath / "exeFiles" / "ui-analyzer",
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


def create_startup_shortcuts(rootPath: Path) -> None:
    wshShell = Dispatch("WScript.Shell")
    pathStartup = _get_special_folder(wshShell=wshShell, name="Startup")
    dictShortcutSpec = _get_shortcut_specs(rootPath=rootPath)

    for strShortcutName in ["LocalServer-LiberRPA", "Executor-LiberRPA"]:
        _create_shortcut(
            wshShell=wshShell,
            shortcutFolder=pathStartup,
            shortcutSpec=dictShortcutSpec[strShortcutName],
        )


def create_desktop_shortcuts(rootPath: Path) -> None:
    wshShell = Dispatch("WScript.Shell")
    pathDesktop = _get_special_folder(wshShell=wshShell, name="Desktop")
    dictShortcutSpec = _get_shortcut_specs(rootPath=rootPath)

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
