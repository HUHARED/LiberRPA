# FileName: _Font.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


import ctypes
import os
from pathlib import Path
import shutil
import winreg


_FONT_FAMILY = "Noto Sans Mono"
_FONT_FILENAME = "NotoSansMono-VariableFont_wdth,wght.ttf"
_FONT_REGISTRY_NAME = f"{_FONT_FAMILY} (TrueType)"
_FONT_REGISTRY_KEY = R"Software\Microsoft\Windows NT\CurrentVersion\Fonts"
_FONT_SOURCE_RELATIVE_PATH = Path(R"envs\assets\font\Noto_Sans_Mono") / _FONT_FILENAME

_WM_FONTCHANGE = 0x001D
_HWND_BROADCAST = 0xFFFF
_SMTO_ABORTIFHUNG = 0x0002
_BROADCAST_TIMEOUT_MS = 3000


def _get_local_app_data(userPath: Path) -> Path:
    strLocalAppData = os.environ.get("LOCALAPPDATA")
    pathLocalAppData = (
        Path(strLocalAppData) if strLocalAppData else userPath / "AppData" / "Local"
    )

    if not pathLocalAppData.is_dir():
        raise FileNotFoundError(f"LOCALAPPDATA does not exist: {pathLocalAppData}")

    return pathLocalAppData.resolve()


def _normalize_windows_path(pathValue: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.expandvars(pathValue)))


def _registry_value_matches_target(registryValue: str, targetPath: Path) -> bool:
    return _normalize_windows_path(registryValue) == _normalize_windows_path(
        str(targetPath)
    )


def _ensure_font_file(rootPath: Path, userPath: Path) -> tuple[Path, bool]:
    pathSource = rootPath / _FONT_SOURCE_RELATIVE_PATH
    if not pathSource.is_file():
        raise FileNotFoundError(f"Bundled font file does not exist: {pathSource}")

    pathUserFontsFolder = (
        _get_local_app_data(userPath=userPath) / "Microsoft" / "Windows" / "Fonts"
    )
    pathUserFontsFolder.mkdir(parents=True, exist_ok=True)

    pathTarget = pathUserFontsFolder / _FONT_FILENAME
    if pathTarget.is_file():
        print(f"Font file already exists: {pathTarget}")
        return pathTarget, False

    shutil.copy2(pathSource, pathTarget)
    print(f"Installed font file: {pathTarget}")
    return pathTarget, True


def _get_registered_font_path() -> str | None:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            _FONT_REGISTRY_KEY,
            0,
            winreg.KEY_QUERY_VALUE,
        ) as key:
            try:
                value, valueType = winreg.QueryValueEx(key, _FONT_REGISTRY_NAME)
            except FileNotFoundError:
                return None
    except FileNotFoundError:
        return None

    if valueType not in (winreg.REG_SZ, winreg.REG_EXPAND_SZ) or not isinstance(
        value, str
    ):
        return None

    return value


def _ensure_font_registry_entry(targetPath: Path) -> bool:
    strCurrentPath = _get_registered_font_path()
    if strCurrentPath is not None and _registry_value_matches_target(
        strCurrentPath, targetPath
    ):
        print(f"Font registry entry already exists: {_FONT_REGISTRY_NAME}")
        return False

    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER,
        _FONT_REGISTRY_KEY,
        0,
        winreg.KEY_SET_VALUE,
    ) as key:
        winreg.SetValueEx(
            key,
            _FONT_REGISTRY_NAME,
            0,
            winreg.REG_SZ,
            str(targetPath),
        )

    if strCurrentPath is None:
        print(f"Registered current-user font: {_FONT_REGISTRY_NAME}")
    else:
        print(f"Repaired current-user font registration: {_FONT_REGISTRY_NAME}")

    return True


def _load_font_for_current_session(targetPath: Path) -> bool:
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    addFontResourceExW = gdi32.AddFontResourceExW
    addFontResourceExW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_void_p]
    addFontResourceExW.restype = ctypes.c_int

    intAdded = addFontResourceExW(str(targetPath), 0, None)
    if intAdded <= 0:
        print(
            f"[Warning] Windows did not load '{_FONT_FAMILY}' into the current session. "
            "The persistent current-user registration is present; sign out or restart Windows if newly started LiberRPA tools still use a fallback font."
        )
        return False

    print(f"Loaded '{_FONT_FAMILY}' into the current Windows session.")
    return True


def _broadcast_font_change() -> None:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    sendMessageTimeoutW = user32.SendMessageTimeoutW
    sendMessageTimeoutW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    sendMessageTimeoutW.restype = ctypes.c_void_p

    result = ctypes.c_size_t()
    sendResult = sendMessageTimeoutW(
        ctypes.c_void_p(_HWND_BROADCAST),
        _WM_FONTCHANGE,
        None,
        None,
        _SMTO_ABORTIFHUNG,
        _BROADCAST_TIMEOUT_MS,
        ctypes.byref(result),
    )

    if not sendResult:
        print(
            "[Warning] The font was installed, but Windows did not confirm the WM_FONTCHANGE broadcast. "
            "Restart running LiberRPA tools if they do not see the font immediately."
        )


def install_font_for_current_user(rootPath: Path, userPath: Path) -> None:
    """Ensure LiberRPA's Noto Sans Mono font is installed for the current Windows user."""
    pathTarget, boolFileChanged = _ensure_font_file(rootPath=rootPath, userPath=userPath)
    boolRegistryChanged = _ensure_font_registry_entry(targetPath=pathTarget)

    if not boolFileChanged and not boolRegistryChanged:
        print(f"The font '{_FONT_FAMILY}' is already installed for the current user.")
        return

    if _load_font_for_current_session(targetPath=pathTarget):
        _broadcast_font_change()

    print(f"The font '{_FONT_FAMILY}' is installed for the current user.")
