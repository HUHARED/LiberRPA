# FileName: LiberRPALocalServer.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


import sys

if len(sys.argv) >= 2 and sys.argv[1] == "--screenshot":
    # Run the real screenshot code and leave.
    from liberrpa.UI._Screenshot import _create_screenshot_manually

    _create_screenshot_manually()
    sys.exit(0)

import multiprocessing
import threading
import time

multiprocessing.freeze_support()

from liberrpa.Common._Utils import PROCESS_NAME

print(f"=== Starting LiberRPALocalServer.py in {PROCESS_NAME} ===")

# Set the log folder name.
from liberrpa.Common._Initialization import set_log_folder_name

set_log_folder_name(folderName="_LiberRPALocalServer")
from liberrpa.Logging import Log

import liberrpa.LiberRPALocalServer._Tray as _Tray

_lockCleanup = threading.Lock()
_boolCleanupStarted = False


def _import_socket_listeners() -> None:
    print("======================================")
    print("=== Import listeners start ===========")
    import liberrpa.LiberRPALocalServer._ListenerSocketConnect  # noqa: F401  # Register Socket.IO listeners.
    import liberrpa.LiberRPALocalServer._ListenerSocketChrome  # noqa: F401  # Register Socket.IO listeners.
    import liberrpa.LiberRPALocalServer._ListenerSocketUiAnalyzer  # noqa: F401  # Register Socket.IO listeners.
    import liberrpa.LiberRPALocalServer._ListenerSocketApplication  # noqa: F401  # Register Socket.IO listeners.
    import liberrpa.LiberRPALocalServer._ListenerSocketRecord  # noqa: F401  # Register Socket.IO listeners.
    import liberrpa.LiberRPALocalServer._ListenerSocketQt  # noqa: F401  # Register Socket.IO listeners.

    print("=== Import listeners done ============")
    print("======================================")


def _start_qt_worker() -> multiprocessing.Process:
    from liberrpa.UI._QtWorker import run_qt_worker
    from liberrpa.UI._Queue import _queueCommand, _queueReturn

    print("Start QtWorker process.")
    processQtWorker = multiprocessing.Process(
        target=run_qt_worker,
        name="QtWorker",
        args=(_queueCommand, _queueReturn),
        daemon=True,
    )
    processQtWorker.start()
    return processQtWorker


def _stop_qt_worker(processQtWorker: multiprocessing.Process | None) -> None:
    if processQtWorker is None:
        return

    if processQtWorker.is_alive():
        try:
            from liberrpa.UI._Queue import send_command_to_qt

            send_command_to_qt(
                command="quit",
                data={},
                timeout=3,
            )
        except Exception as e:
            Log.exception_info(e)

        processQtWorker.join(timeout=3)

    if processQtWorker.is_alive():
        Log.warning("QtWorker did not stop within 3 seconds. Terminate it.")
        processQtWorker.terminate()
        processQtWorker.join(timeout=2)

    if processQtWorker.is_alive():
        Log.error("QtWorker is still running after terminate().")
        return

    try:
        processQtWorker.close()
    except Exception as e:
        Log.exception_info(e)


def _show_exit_notification() -> None:
    try:
        from liberrpa.UI._Queue import send_command_to_qt

        send_command_to_qt(
            command="show_notification",
            data={
                "title": "LiberRPA Local Server",
                "message": "Quit.",
                "duration": 1,
            },
            timeout=3,
        )
        time.sleep(1)
    except Exception as e:
        Log.exception_info(e)


def _cleanup_local_server(
    processQtWorker: multiprocessing.Process | None,
    *,
    boolShowExitNotification: bool,
) -> None:
    global _boolCleanupStarted

    with _lockCleanup:
        if _boolCleanupStarted:
            return
        _boolCleanupStarted = True

    if processQtWorker is None:
        return

    from liberrpa.LiberRPALocalServer._ServerInit import begin_server_shutdown

    begin_server_shutdown()

    try:
        from liberrpa.LiberRPALocalServer import _Hook

        _Hook.stop_active_hook(
            source="local_server_shutdown",
            timeoutSeconds=2,
            raiseOnUnsafe=False,
        )
    except Exception as e:
        Log.exception_info(e)

    if boolShowExitNotification:
        _show_exit_notification()

    _stop_qt_worker(processQtWorker)


def _main() -> int:
    processQtWorker: multiprocessing.Process | None = None

    try:
        print("=== '__main__' block is running ===")

        from liberrpa.Common._BasicConfig import get_local_server_port
        from liberrpa.Common._Utils import STR_PROJECT_ROOT
        from liberrpa.LiberRPALocalServer._ServerInit import (
            create_flask_server,
            should_start_flask_server,
        )

        intPort = get_local_server_port()
        if not should_start_flask_server(port=intPort):
            return 0

        # Validate all listener imports before starting process-owned helpers.
        _import_socket_listeners()
        processQtWorker = _start_qt_worker()

        print("LiberRPA Local Server running in " + STR_PROJECT_ROOT)

        _Tray.run_tray(
            shutdownCallback=lambda: _cleanup_local_server(
                processQtWorker,
                boolShowExitNotification=True,
            )
        )
        create_flask_server(port=intPort)
        return 0
    except Exception as e:
        Log.exception_info(e)
        return 1
    finally:
        _Tray.stop_tray()
        _cleanup_local_server(
            processQtWorker,
            boolShowExitNotification=False,
        )


if __name__ == "__main__":
    raise SystemExit(_main())
