# FileName: LiberRPALocalServer.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


import multiprocessing


processName = multiprocessing.current_process().name
print(f"=== Starting LiberRPALocalServer.py in {processName} ===")


if __name__ == "__main__":
    try:
        print("=== '__main__' block is running ===")
        # Set the log folder name.
        # Run it before multiprocessing.freeze_support() to avoid the error after quitting.
        # ========================
        from liberrpa.Common._Initialization import set_log_folder_name

        set_log_folder_name(folderName="_LiberRPALocalServer")
        from liberrpa.Logging import Log

        # ========================

        # run freeze_support() to avoid re-running of it was packaged to an exe.
        multiprocessing.freeze_support()

        print("Start QtWorker process.")
        from liberrpa.UI._QtWorker import run_qt_worker
        from liberrpa.UI._Queue import queueCommand, queueReturn

        p = multiprocessing.Process(
            target=run_qt_worker, name="QtWorker", args=(queueCommand, queueReturn), daemon=True
        )
        p.start()

        import os

        print("LiberRPA Local Server running in " + os.getcwd())

        from liberrpa.Dialog import show_notification

        # The server take a little time to start, so, show the notification to make user know.
        # show_notification(title="LiberRPA Local Server", message="Try to launch...", duration=2, wait=False)

        from exe.LiberRPALocalServer._ServerInit import boolHasRunServer, create_flask_server

        # Import listeners
        # ========================
        print("======================================")
        print("=== Import listeners start ===========")
        import exe.LiberRPALocalServer._ListenerSocketConnect
        import exe.LiberRPALocalServer._ListenerSocketChrome
        import exe.LiberRPALocalServer._ListenerSocketUiAnalyzer
        import exe.LiberRPALocalServer._ListenerSocketApplication
        import exe.LiberRPALocalServer._ListenerSocketRecord
        import exe.LiberRPALocalServer._ListenerSocketQt

        print("=== Import listeners done ============")
        print("======================================")

        # ========================

        # Create system tray icon.
        import exe.LiberRPALocalServer._Tray as _Tray

        _Tray.run_tray()

        from liberrpa.Common._BasicConfig import get_basic_config_dict

        dictTemp = get_basic_config_dict()
        Log.info(f"EditorConfig = {dictTemp}")
        create_flask_server(port=int(dictTemp["localServerPort"]))
    except Exception as e:
        Log.exception_info(e)
    finally:
        """Log.critical("Quit the server. __main__")
        if not boolHasRunServer:
            show_notification(title="LiberRPA Local Server", message="Quit.", duration=1, wait=True)

        from liberrpa.UI._Queue import send_command_to_qt

        send_command_to_qt(command="quit", data={})

        # Force exiting for stop Other logic.
        Log.critical("__main__ os._exit(0)")

        import time

        time.sleep(0.5)
        os._exit(0)"""
        pass
