# FileName: _Tray.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._BasicConfig import get_liberrpa_ico_path
from liberrpa.Dialog import show_notification


from pystray import Icon, Menu, MenuItem
from PIL import Image
import os
import threading
from typing import Literal, NoReturn

_iconTray: object | None = None
_threadTray: threading.Thread | None = None
_lockTray = threading.Lock()  # Ensure only one logic changes the icon at the same time.


@Log.trace()
def stop_tray() -> None:
    global _iconTray

    with _lockTray:
        icon = _iconTray
        _iconTray = None

    if icon is not None:
        icon.stop()  # type: ignore - It's Icon


def _exit_process_after_tray_stops(
    threadTray: threading.Thread | None,
) -> NoReturn:
    if threadTray is not None and threadTray is not threading.current_thread():
        threadTray.join(timeout=2)

    if threadTray is not None and threadTray.is_alive():
        Log.warning("The tray thread did not stop within 2 seconds.")

    try:
        show_notification(
            title="LiberRPA Local Server",
            message="Quit.",
            duration=1,
            wait=True,
        )
    except Exception as e:
        Log.exception_info(e)

    try:
        from liberrpa.UI._Queue import send_command_to_qt

        send_command_to_qt(command="quit", data={})
    except Exception as e:
        Log.exception_info(e)

    Log.critical("_Tray os._exit(0)")
    os._exit(0)


@Log.trace()
def _stop_server() -> None:
    Log.critical("Quit the server. _Tray")

    with _lockTray:
        threadTray = _threadTray

    stop_tray()

    # The menu callback must return before the pystray event loop can exit.
    threading.Thread(
        target=_exit_process_after_tray_stops,
        name="LiberRPALocalServerExit",
        args=(threadTray,),
        daemon=False,
    ).start()


def stop_server(
    _iconTrayCallback: object,
    _menuItem: object,
) -> None:
    _stop_server()


def _load_icon_image(component: Literal["LiberRPALocalServer", "LiberRPALocalServer_Indicating"]) -> Image.Image:

    # Use copy() so the file handle is closed immediately. This avoids possible file locking problems on Windows.
    with Image.open(get_liberrpa_ico_path(component=component)) as img:
        return img.copy()


@Log.trace()
def setup_tray_icon() -> None:
    global _iconTray

    imgIcon = _load_icon_image(component="LiberRPALocalServer")
    menu = Menu(
        MenuItem("Exit", stop_server),
    )
    iconTray = Icon(
        name="LiberRPA",
        icon=imgIcon,
        title="LiberRPA Local Server",
        menu=menu,
    )

    with _lockTray:
        _iconTray = iconTray

    try:
        iconTray.run()
    finally:
        with _lockTray:
            if _iconTray is iconTray:
                _iconTray = None


@Log.trace()
def change_tray_icon(component: Literal["LiberRPALocalServer", "LiberRPALocalServer_Indicating"]) -> None:
    imgIcon = _load_icon_image(component=component)

    with _lockTray:
        if _iconTray is None:
            Log.warning("Tray icon has not been initialized yet.")
            return

        _iconTray.icon = imgIcon  # type: ignore - It's Icon


@Log.trace()
def run_tray() -> None:
    global _threadTray

    threadTray = threading.Thread(
        target=setup_tray_icon,
        name="LiberRPATray",
        daemon=True,
    )

    with _lockTray:
        _threadTray = threadTray

    threadTray.start()
