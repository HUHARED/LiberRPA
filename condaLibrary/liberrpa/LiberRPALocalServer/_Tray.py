# FileName: _Tray.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._BasicConfig import get_liberrpa_ico_path


from pystray import Icon, Menu, MenuItem
from PIL import Image
import logging
import os
import sys
import threading
from collections.abc import Callable
from typing import Literal, NoReturn

_iconTray: object | None = None
_threadTray: threading.Thread | None = None
_shutdownCallback: Callable[[], None] | None = None
_boolExitStarted = False
_SHUTDOWN_CALLBACK_TIMEOUT_SECONDS = 12
_lockTray = (
    threading.Lock()
)  # Ensure only one logic changes the tray lifecycle at the same time.


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
    shutdownCallback: Callable[[], None] | None,
) -> NoReturn:
    if threadTray is not None and threadTray is not threading.current_thread():
        threadTray.join(timeout=2)

    if threadTray is not None and threadTray.is_alive():
        Log.warning("The tray thread did not stop within 2 seconds.")

    if shutdownCallback is not None:

        def run_shutdown_callback() -> None:
            try:
                shutdownCallback()
            except Exception as e:
                Log.exception_info(e)

        threadCleanup = threading.Thread(
            target=run_shutdown_callback,
            name="LiberRPALocalServerCleanup",
            daemon=True,
        )
        threadCleanup.start()
        threadCleanup.join(timeout=_SHUTDOWN_CALLBACK_TIMEOUT_SECONDS)
        if threadCleanup.is_alive():
            Log.warning(
                "Local Server shutdown cleanup did not finish within "
                f"{_SHUTDOWN_CALLBACK_TIMEOUT_SECONDS} seconds."
            )

    # Flask-SocketIO is running synchronously in the main thread. After explicitly stopping process-owned helpers and flushing logs, use a process exit as the final fallback so the tray command cannot leave a hidden server behind.
    Log.critical("Exit LiberRPA Local Server after explicit shutdown cleanup.")
    logging.shutdown()

    try:
        sys.stdout.flush()
        sys.stderr.flush()
    finally:
        os._exit(0)


@Log.trace()
def _stop_server() -> None:
    global _boolExitStarted

    with _lockTray:
        if _boolExitStarted:
            Log.debug("Local Server exit has already started.")
            return

        _boolExitStarted = True
        threadTray = _threadTray
        shutdownCallback = _shutdownCallback

    Log.critical("Quit the server from the tray menu.")
    stop_tray()

    # The menu callback must return before the pystray event loop can exit.
    threading.Thread(
        target=_exit_process_after_tray_stops,
        name="LiberRPALocalServerExit",
        args=(threadTray, shutdownCallback),
        daemon=False,
    ).start()


def stop_server(
    _iconTrayCallback: object,
    _menuItem: object,
) -> None:
    _stop_server()


def _load_icon_image(
    component: Literal["LiberRPALocalServer", "LiberRPALocalServer_Indicating"],
) -> Image.Image:
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
def change_tray_icon(
    component: Literal["LiberRPALocalServer", "LiberRPALocalServer_Indicating"],
) -> None:
    imgIcon = _load_icon_image(component=component)

    with _lockTray:
        if _iconTray is None:
            Log.warning("Tray icon has not been initialized yet.")
            return

        _iconTray.icon = imgIcon  # type: ignore - It's Icon


@Log.trace()
def run_tray(*, shutdownCallback: Callable[[], None]) -> None:
    global _boolExitStarted, _shutdownCallback, _threadTray

    threadTray = threading.Thread(
        target=setup_tray_icon,
        name="LiberRPATray",
        daemon=True,
    )

    with _lockTray:
        _boolExitStarted = False
        _shutdownCallback = shutdownCallback
        _threadTray = threadTray

    threadTray.start()
