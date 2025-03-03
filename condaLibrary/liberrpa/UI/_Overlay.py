# FileName: _Overlay.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Common._WebSocket import send_command
import time


def create_overlay(
    x: int, y: int, width: int, height: int, color: str = "red", duration: int = 1000, label: str = ""
) -> None:
    dictCommand = {
        "commandName": "create_overlay",
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "color": color,
        "duration": duration,
        "label": label,
    }
    send_command(eventName="qt_command", command=dictCommand)


if __name__ == "__main__":
    from liberrpa.Logging import Log
    import time

    Log.debug("Start")
    create_overlay(100, 100, 100, 100, "red", 3000, label="0 ABC 中文 0123456789 0123456789 0123456789")
    time.sleep(1)
    create_overlay(100, 100, 100, 100, "red", 3000, label="0 ABC 中文 0123456789 0123456789 0123456789")
    Log.debug("Done")
