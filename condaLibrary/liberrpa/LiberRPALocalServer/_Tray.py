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
_TRAY_STOP_TIMEOUT_SECONDS = 2
_SHUTDOWN_CALLBACK_TIMEOUT_SECONDS = 12
_LOG_SHUTDOWN_TIMEOUT_SECONDS = 2
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


def _shutdown_logging(
    *,
    boolTrayStillRunning: bool,
    boolCleanupStillRunning: bool,
) -> None:
    """Flush shutdown diagnostics without blocking the exit coordinator."""
    try:
        if boolTrayStillRunning:
            Log.warning(
                f"The tray thread did not stop within {_TRAY_STOP_TIMEOUT_SECONDS} seconds."
            )
        if boolCleanupStillRunning:
            Log.warning(
                "Local Server shutdown cleanup did not finish within "
                f"{_SHUTDOWN_CALLBACK_TIMEOUT_SECONDS} seconds."
            )

        Log.critical("Exit LiberRPA Local Server after explicit shutdown cleanup.")
        logging.shutdown()
    finally:
        # pythonw.exe may have no standard streams.
        # A missing or closed stream must not prevent flushing the other stream or finishing shutdown.
        for stream in (sys.stdout, sys.stderr):
            if stream is not None:
                try:
                    stream.flush()
                except Exception:
                    # Do not use the logging system after shutting it down.
                    pass


def _exit_process_after_tray_stops(
    threadTray: threading.Thread | None,
    shutdownCallback: Callable[[], None] | None,
) -> NoReturn:
    # This coordinator must never call Log, flush a stream, or run cleanup directly: any of those operations can wait indefinitely on another thread.
    boolTrayStillRunning = False
    boolCleanupStillRunning = False

    try:
        if threadTray is not None and threadTray is not threading.current_thread():
            threadTray.join(timeout=_TRAY_STOP_TIMEOUT_SECONDS)

        boolTrayStillRunning = threadTray is not None and threadTray.is_alive()

        if shutdownCallback is not None:

            def run_shutdown_callback() -> None:
                try:
                    shutdownCallback()
                except Exception as e:
                    # Reporting an error may itself block.
                    # Keep it in the bounded cleanup worker, never in the exit coordinator.
                    Log.exception_info(e)

            threadCleanup = threading.Thread(
                target=run_shutdown_callback,
                name="LiberRPALocalServerCleanup",
                daemon=True,
            )
            threadCleanup.start()
            threadCleanup.join(timeout=_SHUTDOWN_CALLBACK_TIMEOUT_SECONDS)
            boolCleanupStillRunning = threadCleanup.is_alive()
    finally:
        try:
            # logging.shutdown() waits for handler locks and may never return.
            # Give final diagnostics and standard-stream flushing a short, bounded opportunity to complete in a separate daemon thread.
            threadLogging = threading.Thread(
                target=_shutdown_logging,
                name="LiberRPALocalServerLogShutdown",
                kwargs={
                    "boolTrayStillRunning": boolTrayStillRunning,
                    "boolCleanupStillRunning": boolCleanupStillRunning,
                },
                daemon=True,
            )
            threadLogging.start()
            threadLogging.join(timeout=_LOG_SHUTDOWN_TIMEOUT_SECONDS)
        finally:
            # Flask-SocketIO still runs in the main thread.
            # Only this final process exit is independent of helper threads and logging locks.
            os._exit(0)


def _stop_server() -> None:
    # Do not add @Log.trace(): start the exit coordinator before the first log call so a blocked logging handler cannot prevent shutdown from starting.
    global _boolExitStarted

    with _lockTray:
        if _boolExitStarted:
            return

        _boolExitStarted = True
        threadTray = _threadTray
        shutdownCallback = _shutdownCallback

    # The menu callback must return before the pystray event loop can exit.
    # Start the coordinator before logging or stopping the tray; it bounds shutdown even if either of those operations blocks or raises.
    try:
        threading.Thread(
            target=_exit_process_after_tray_stops,
            name="LiberRPALocalServerExit",
            args=(threadTray, shutdownCallback),
            daemon=False,
        ).start()
    except Exception:
        # No coordinator was started, so do not leave a hidden server behind.
        # Logging this failure could block for the same reason as normal exit.
        os._exit(1)

    try:
        Log.critical("Quit the server from the tray menu.")
    finally:
        stop_tray()


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
