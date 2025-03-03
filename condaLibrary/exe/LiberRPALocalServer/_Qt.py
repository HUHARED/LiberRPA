# FileName: _Qt.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.UI._Queue import send_command_to_qt

import time
from typing import Literal


@Log.trace()
def show_notification(title: str, message: str, duration: int = 1, wait: bool = True) -> None:

    send_command_to_qt(
        command="show_notification",
        data={"title": title, "message": message, "duration": duration},
    )
    # QtWorker didn't wait the command completed, so wait here.
    if wait:
        time.sleep(duration)


def create_overlay(
    x: int, y: int, width: int, height: int, color: str = "red", duration: int = 1000, label: str = ""
) -> None:
    # print("create_overlay before send command to qt")
    send_command_to_qt(
        command="create_overlay",
        data={"x": x, "y": y, "width": width, "height": height, "color": color, "duration": duration, "label": label},
    )
    # QtWorker didn't wait the command completed, so wait here.
    time.sleep(duration / 1000)
    # print("create_overlay sleeps done.")


class ScreenPrintObj(str):
    pass


# Save all ScreenPrint area of each Python client, when a Python client disconnect, close all its area.
dictClientAreaCache: dict[str, list[ScreenPrintObj]] = {}


@Log.trace()
def create_area(
    x: int = 0,
    y: int = 0,
    width: int = 400,
    height: int = 200,
    fontFamily: str = "Roboto Mono",
    fontSize: int = 16,
    fontColor: Literal["red", "green", "blue", "yellow", "purple", "pink", "black"] = "red",
) -> ScreenPrintObj:
    screenPrintObj: ScreenPrintObj = send_command_to_qt(
        command="create_area",
        data={
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "fontFamily": fontFamily,
            "fontSize": fontSize,
            "fontColor": fontColor,
        },
    )  # type: ignore - It will be ScreenPrintObj

    return screenPrintObj


@Log.trace()
def display_text(screenPrintObj: ScreenPrintObj, text: str) -> None:
    send_command_to_qt(command="display_text", data={"screenPrintObj": screenPrintObj, "text": text})


@Log.trace()
def clean_text(screenPrintObj: ScreenPrintObj) -> None:
    send_command_to_qt(command="clean_text", data={"screenPrintObj": screenPrintObj})


@Log.trace()
def close_area(screenPrintObj: ScreenPrintObj) -> None:
    send_command_to_qt(command="close_area", data={"screenPrintObj": screenPrintObj})
