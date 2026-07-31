# FileName: LiberRPALocalServer.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


import sys

if len(sys.argv) >= 2 and sys.argv[1] == "--screenshot":
    # Run the real screenshot code and leave
    from liberrpa.UI._Screenshot import _create_screenshot_manually

    _create_screenshot_manually()
    sys.exit(0)

import multiprocessing

multiprocessing.freeze_support()

from liberrpa.Common._Utils import PROCESS_NAME

print(f"=== Starting LiberRPALocalServer.py in {PROCESS_NAME} ===")

# Set the log folder name.
from liberrpa.Common._Initialization import set_log_folder_name

set_log_folder_name(folderName="_LiberRPALocalServer")
from liberrpa.Logging import Log

import liberrpa.LiberRPALocalServer._Tray as _Tray

if __name__ == "__main__":
    try:
        print("=== '__main__' block is running ===")

        from liberrpa.Common._Utils import STR_PROJECT_ROOT

        print("Start QtWorker process.")
        from liberrpa.UI._QtWorker import run_qt_worker
        from liberrpa.UI._Queue import _queueCommand, _queueReturn

        p = multiprocessing.Process(
            target=run_qt_worker, name="QtWorker", args=(_queueCommand, _queueReturn), daemon=True
        )
        p.start()

        print("LiberRPA Local Server running in " + STR_PROJECT_ROOT)

        # from liberrpa.Dialog import show_notification

        # The server take a little time to start, so, show the notification to make user know.
        # show_notification(title="LiberRPA Local Server", message="Try to launch...", duration=2, wait=False)

        from liberrpa.LiberRPALocalServer._ServerInit import create_flask_server

        # Import listeners
        # ========================
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

        # ========================

        # Create system tray icon.
        _Tray.run_tray()

        from liberrpa.Common._BasicConfig import get_local_server_port

        create_flask_server(port=get_local_server_port())
    except Exception as e:
        Log.exception_info(e)
    finally:
        _Tray.stop_tray()
