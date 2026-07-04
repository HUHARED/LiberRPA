# FileName: _Tray.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._BasicConfig import get_liberrpa_ico_path
from liberrpa.Dialog import show_notification


from pystray import Icon, MenuItem
from PIL import Image
import os
import threading
import time
from typing import Any, Literal, NoReturn

_iconTray: Any | None = None
_lockTray = threading.Lock()  # Ensure only one logic changes the icon at the same time.


@Log.trace()
def stop_server() -> NoReturn:
    Log.critical("Quit the server. _Tray")
    show_notification(title="LiberRPA Local Server", message="Quit.", duration=1, wait=True)

    from liberrpa.UI._Queue import send_command_to_qt

    send_command_to_qt(command="quit", data={})

    # Force exiting for stop Other logic.
    Log.critical("_Tray os._exit(0)")

    time.sleep(0.5)
    os._exit(0)


def _load_icon_image(component: Literal["LiberRPALocalServer", "LiberRPALocalServer_Indicating"]) -> Image.Image:

    # Use copy() so the file handle is closed immediately. This avoids possible file locking problems on Windows.
    with Image.open(get_liberrpa_ico_path(component=component)) as img:
        return img.copy()


@Log.trace()
def setup_tray_icon() -> None:
    global _iconTray

    imgIcon = _load_icon_image(component="LiberRPALocalServer")
    menu = (MenuItem("Exit", stop_server),)

    icon = Icon(
        name="LiberRPA",
        icon=imgIcon,
        title="LiberRPA Local Server",
        menu=menu,
    )

    with _lockTray:
        _iconTray = icon

    icon.run()


@Log.trace()
def change_tray_icon(component: Literal["LiberRPALocalServer", "LiberRPALocalServer_Indicating"]) -> None:
    imgIcon = _load_icon_image(component=component)

    with _lockTray:
        if _iconTray is None:
            Log.warning("Tray icon has not been initialized yet.")
            return

        _iconTray.icon = imgIcon


@Log.trace()
def run_tray() -> None:
    threadTray = threading.Thread(target=setup_tray_icon, daemon=True)
    threadTray.start()
