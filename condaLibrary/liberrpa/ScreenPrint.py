# FileName: ScreenPrint.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._WebSocket import send_command

from typing import Literal


class ScreenPrintObj(str):
    pass


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
    """
    Creates and displays a floating text display area.

    Parameters:
        x: The x-coordinate of the top-left corner of the window.
        y: The y-coordinate of the top-left corner of the window.
        width: The width of the window.
        height: The height of the window.
        fontFamily: The font family for displaying text.
        fontSize: The font size of the text.
        fontColor: The text color. Must be one of ["red", "green", "blue", "yellow", "purple", "pink", "black"].

    Returns:
        ScreenPrintObj: An instance of the floating text display window.
    """

    dictCommand = {
        "commandName": "create_area",
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "fontFamily": fontFamily,
        "fontSize": fontSize,
        "fontColor": fontColor,
    }

    screenPrintObj: ScreenPrintObj = send_command(eventName="qt_command", command=dictCommand)

    return screenPrintObj


@Log.trace()
def display_text(screenPrintObj: ScreenPrintObj, text: str) -> None:
    """
    Displays the specified text in the floating text display area.

    Parameters:
        screenPrintObj: The ScreenPrintObj instance where the text will be displayed.
        text: The text to display.
    """
    dictCommand = {
        "commandName": "display_text",
        "screenPrintObj": screenPrintObj,
        "text": text,
    }

    send_command(eventName="qt_command", command=dictCommand)


@Log.trace()
def clean_text(screenPrintObj: ScreenPrintObj) -> None:
    """
    Clears all text from the floating text display area.

    Parameters:
        screenPrintObj: The ScreenPrintObj instance to be cleared.
    """

    dictCommand = {
        "commandName": "clean_text",
        "screenPrintObj": screenPrintObj,
    }

    send_command(eventName="qt_command", command=dictCommand)


@Log.trace()
def close_area(screenPrintObj: ScreenPrintObj) -> None:
    """
    Closes the floating text display window.

    Parameters:
        screenPrintObj: The ScreenPrintObj instance to be closed.
    """
    dictCommand = {
        "commandName": "close_area",
        "screenPrintObj": screenPrintObj,
    }

    send_command(eventName="qt_command", command=dictCommand)


if __name__ == "__main__":

    import time

    screenPrintObj = create_area(
        x=0, y=0, width=400, height=200, fontFamily="Roboto Mono", fontSize=14, fontColor="red"
    )
    screenPrintObj2 = create_area(
        x=500, y=0, width=400, height=200, fontFamily="Roboto Mono", fontSize=14, fontColor="yellow"
    )
    time.sleep(1)
    for i in range(1, 50, 1):
        time.sleep(0.2)
        print(i)
        display_text(screenPrintObj=screenPrintObj, text=str(i) * 30)
        display_text(screenPrintObj=screenPrintObj2, text=str(i) * 30)
        if i % 15 == 0:
            time.sleep(1)
            clean_text(screenPrintObj=screenPrintObj)
    close_area(screenPrintObj=screenPrintObj)
    time.sleep(1)
