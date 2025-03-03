# FileName: Mouse.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
import liberrpa.UI._UiElement as _UiElement
from liberrpa.Common._TypedValue import (
    MouseButton,
    ClickMode,
    FivePosition,
    ExecutionMode,
    DictUiaAttr,
    DictHtmlAttr,
    DictImageAttr,
    DictPosition,
    SelectorWindow,
    SelectorUia,
    SelectorHtml,
    SelectorImage,
)
from liberrpa.UI._TerminableThread import timeout_kill_thread
from liberrpa.Common._Exception import UiOperationError
from liberrpa.Basic import delay
from liberrpa.Common._Chrome import click_mouse_event

import uiautomation
import pyautogui
from pynput.mouse import Controller
from typing import Literal


mouse = Controller()


def _check_mouse_button(button: MouseButton) -> None:
    listValue = ["left", "right", "middle"]
    if button not in listValue:
        raise ValueError(f"The argument button({button}) should be one of {listValue}")


def _check_mouse_click_mode(clickMode: ClickMode) -> None:
    listValue = ["single_click", "double_click", "down", "up"]
    if clickMode not in listValue:
        raise ValueError(f"The argument clickMode({clickMode}) should be one of {listValue}")


def _check_five_position(position: FivePosition) -> None:
    listValue = ["center", "top_left", "top_right", "bottom_left", "bottom_right"]
    if position not in listValue:
        raise ValueError(f"The argument position({position}) should be one of {listValue}")


def _get_5_coordinates(dictAttr: DictUiaAttr | DictHtmlAttr | DictImageAttr) -> dict[str, tuple[int, int]]:
    """Calculate the coordinates of different positon of uiTarget."""
    intX = int(dictAttr["secondary-x"])
    intY = int(dictAttr["secondary-y"])
    intWidth = int(dictAttr["secondary-width"])
    intHeight = int(dictAttr["secondary-height"])
    center = (int(intX + intWidth / 2), int(intY + intHeight / 2))
    top_left = (intX, intY)
    top_right = (intX + intWidth - 1, intY)
    bottom_left = (intX, intY + intHeight - 1)
    bottom_right = (intX + intWidth - 1, intY + intHeight - 1)

    dictReturn = {
        "center": center,
        "top_left": top_left,
        "top_right": top_right,
        "bottom_left": bottom_left,
        "bottom_right": bottom_right,
    }

    return dictReturn


@Log.trace()
def get_mouse_position() -> DictPosition:
    """
    Retrieves the current physical position of the cursor on the screen.

    Returns:
        DictPosition: A dictionary like {"x": x, "y": y}
    """
    x, y = uiautomation.GetPhysicalCursorPos()

    return {"x": x, "y": y}


def _click_element(
    selector: SelectorWindow | SelectorUia | SelectorHtml | SelectorImage,
    offsetX: int = 0,
    offsetY: int = 0,
    button: MouseButton = "left",
    clickMode: ClickMode = "single_click",
    executionMode: ExecutionMode = "simulate",
    position: FivePosition = "center",
    pressCtrl: bool = False,
    pressShift: bool = False,
    pressAlt: bool = False,
    pressWin: bool = False,
    duration: int = 0,
    timeout: int = 10000,
    preExecutionDelay: int = 300,
    postExecutionDelay: int = 200,
) -> None:
    _check_mouse_button(button=button)
    _check_mouse_click_mode(clickMode=clickMode)
    _UiElement.check_execution_type(executionMode=executionMode)
    _check_five_position(position=position)

    # Call Chrome to do html element api click.
    if selector.get("category") == "html" and executionMode == "api":
        if position != "center":
            Log.warning(
                "The argument position is useless when clicking an html element by 'api', it will just send a click event to the element."
            )
        if duration != 0:
            Log.warning(
                "The argument duration will always be 0 when clicking an html element by 'api', due to it will just send a click event to the element."
            )
        _UiElement.activate_element_window(selector=selector)
        click_mouse_event(
            htmlSelector=selector["specification"],  # type: ignore - it's SelectorHtml
            button=button,
            clickMode=clickMode,
            pressCtrl=pressCtrl,
            pressShift=pressShift,
            pressAlt=pressAlt,
            pressWin=pressWin,
            preExecutionDelay=preExecutionDelay,
            timeout=timeout,
        )
        delay(postExecutionDelay)
        return None

    if selector.get("category") == "image" and executionMode != "simulate":
        raise UiOperationError("Only support 'simulate' click for an image element")

    # The simulate click, and uia api click.

    uiTarget, dictTarget = _UiElement.get_element_with_pre_delay(selector=selector, preExecutionDelay=preExecutionDelay)

    dictCoordinates = _get_5_coordinates(dictAttr=dictTarget)

    match executionMode:
        case "simulate":
            # Use pyautogui
            pyautogui.moveTo(
                x=dictCoordinates[position][0] + offsetX,
                y=dictCoordinates[position][1] + offsetY,
                duration=duration / 1000,
            )
            _UiElement.modifier_keys_down_pyautogui(
                pressCtrl=pressCtrl, pressShift=pressShift, pressAlt=pressAlt, pressWin=pressWin
            )
            match clickMode:
                case "single_click":
                    pyautogui.click(button=button)
                case "double_click":
                    pyautogui.doubleClick(button=button)
                case "down":
                    pyautogui.mouseDown(button=button)
                case "up":
                    pyautogui.mouseUp(button=button)
            _UiElement.modifier_keys_up_pyautogui(
                pressCtrl=pressCtrl, pressShift=pressShift, pressAlt=pressAlt, pressWin=pressWin
            )

        case "api":
            if isinstance(uiTarget, uiautomation.Control):
                # The uia control element
                # When use uiautomation, can only execute a simple mouse_left single click behavior. Maybe use ctypes to achieve more functions later.
                if (
                    button == "left"
                    and clickMode == "single_click"
                    and position == "center"
                    and offsetX == 0
                    and offsetY == 0
                    and pressCtrl == False
                    and pressShift == False
                    and pressAlt == False
                    and pressWin == False
                    and duration == 0
                ):
                    boolFoundPattern = False

                    for patternId, method in [
                        (uiautomation.PatternId.InvokePattern, "Invoke"),
                        (uiautomation.PatternId.TogglePattern, "Toggle"),
                        (uiautomation.PatternId.SelectionItemPattern, "Select"),
                    ]:
                        pattern = uiTarget.GetPattern(patternId)
                        if pattern:
                            # Get and call the method by ()
                            getattr(pattern, method)()
                            boolFoundPattern = True
                            break

                    if boolFoundPattern == False:
                        raise UiOperationError("The target element didn't support 'api' method. selector: {selector}")
                else:
                    raise UiOperationError(
                        "When use 'api' method to click an uia element, only a simple mouse_left single click is supported. selector: {selector}"
                    )
            else:
                # html or image element api click
                raise UiOperationError(
                    "(!!!It should not appear.) Use api mode for html or image element should have be handle!!! selector: {selector}"
                )

    delay(postExecutionDelay)


@Log.trace()
def click_element(
    selector: SelectorWindow | SelectorUia | SelectorHtml | SelectorImage,
    offsetX: int = 0,
    offsetY: int = 0,
    button: MouseButton = "left",
    clickMode: ClickMode = "single_click",
    executionMode: ExecutionMode = "simulate",
    position: FivePosition = "center",
    pressCtrl: bool = False,
    pressShift: bool = False,
    pressAlt: bool = False,
    pressWin: bool = False,
    duration: int = 0,
    timeout: int = 10000,
    preExecutionDelay: int = 300,
    postExecutionDelay: int = 200,
) -> None:
    """
    Click an element.

    Parameters:
        selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
        offsetX: Horizontal offset from the element's specified click position (in pixels). Only works when executionMode is "simulate".
        offsetY: Vertical offset from the element's specified click position (in pixels). Only works when executionMode is "simulate".
        button: Specifies which mouse button to click. Options are "left", "right", and "middle".
        clickMode: Defines the type of click to perform. Options are "single_click", "double_click", "down", and "up".
        executionMode: Options are "simulate" and "api". "simulate" will move the cursor, support all arguements of the function. "api" will not move the cursor, it can handle some situations that the target element be covered, but it supports less arguments than "simulate".
        position: Specifies where on the element to click. Options are "center", "top_left", "top_right", "bottom_left", and "bottom_right". It will only work if executionMode is "simulate".
        pressCtrl: If True, holds the Ctrl key during the click.
        pressShift: If True, holds the Shift key during the click.
        pressAlt: If True, holds the Alt key during the click.
        pressWin: If True, holds the Windows key during the click.
        duration: Time to move the mouse to the target position (in seconds). If it is 0, it moves to "position" immediately.
        timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the function doesn't completed after "timeout", it will throw an UiTimeoutError.
        preExecutionDelay: Time to wait before performing the action (in milliseconds).
        postExecutionDelay: Time to wait after performing the action (in milliseconds).
    """
    timeout = _UiElement.check_set_timeout(timeout=timeout)

    return timeout_kill_thread(timeout=timeout)(_click_element)(
        selector,
        offsetX,
        offsetY,
        button,
        clickMode,
        executionMode,
        position,
        pressCtrl,
        pressShift,
        pressAlt,
        pressWin,
        duration,
        timeout,
        preExecutionDelay,
        postExecutionDelay,
    )


def _move_to_element(
    selector: SelectorWindow | SelectorUia | SelectorHtml | SelectorImage,
    offsetX: int = 0,
    offsetY: int = 0,
    position: FivePosition = "center",
    duration: int = 0,
    preExecutionDelay: int = 300,
    postExecutionDelay: int = 200,
) -> None:

    _check_five_position(position=position)

    _, dictTarget = _UiElement.get_element_with_pre_delay(selector=selector, preExecutionDelay=preExecutionDelay)

    dictCoordinates = _get_5_coordinates(dictAttr=dictTarget)
    # Use pyautogui
    pyautogui.moveTo(
        x=dictCoordinates[position][0] + offsetX,
        y=dictCoordinates[position][1] + offsetY,
        duration=duration / 1000,
    )

    delay(postExecutionDelay)


@Log.trace()
def move_to_element(
    selector: SelectorWindow | SelectorUia | SelectorHtml | SelectorImage,
    offsetX: int = 0,
    offsetY: int = 0,
    position: FivePosition = "center",
    duration: int = 0,
    timeout: int = 10000,
    preExecutionDelay: int = 300,
    postExecutionDelay: int = 200,
) -> None:
    """
    Move to element.

    Parameters:
        selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
        offsetX: Horizontal offset from the element's specified click position (in pixels). Only works when executionMode is "simulate".
        offsetY: Vertical offset from the element's specified click position (in pixels). Only works when executionMode is "simulate".
        position: Specifies where on the element to click. Options are "center", "top_left", "top_right", "bottom_left", and "bottom_right". It will only work if executionMode is "simulate".
        duration: Time to move the mouse to the target position (in seconds). If it is 0, it moves to "position" immediately.
        timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the function doesn't completed after "timeout", it will throw an UiTimeoutError.
        preExecutionDelay: Time to wait before performing the action (in milliseconds).
        postExecutionDelay: Time to wait after performing the action (in milliseconds).
    """
    timeout = _UiElement.check_set_timeout(timeout=timeout)
    return timeout_kill_thread(timeout=timeout)(_move_to_element)(
        selector,
        offsetX,
        offsetY,
        position,
        duration,
        preExecutionDelay,
        postExecutionDelay,
    )


@Log.trace()
def click(
    button: MouseButton = "left",
    clickMode: ClickMode = "single_click",
    pressCtrl: bool = False,
    pressShift: bool = False,
    pressAlt: bool = False,
    pressWin: bool = False,
    preExecutionDelay: int = 300,
    postExecutionDelay: int = 200,
) -> None:
    """
    Mouse click.

    Parameters:
        button: Specifies which mouse button to click. Options are "left", "right", and "middle".
        clickMode: Defines the type of click to perform. Options are "single_click", "double_click", "down", and "up".
        pressCtrl: If True, holds the Ctrl key during the click.
        pressShift: If True, holds the Shift key during the click.
        pressAlt: If True, holds the Alt key during the click.
        pressWin: If True, holds the Windows key during the click.
        preExecutionDelay: Time to wait before performing the action (in milliseconds).
        postExecutionDelay: Time to wait after performing the action (in milliseconds).
    """
    _check_mouse_button(button=button)
    _check_mouse_click_mode(clickMode=clickMode)

    delay(preExecutionDelay)

    _UiElement.modifier_keys_down_pyautogui(
        pressCtrl=pressCtrl, pressShift=pressShift, pressAlt=pressAlt, pressWin=pressWin
    )

    match clickMode:
        case "single_click":
            pyautogui.click(button=button)
        case "double_click":
            pyautogui.doubleClick(button=button)
        case "down":
            pyautogui.mouseDown(button=button)
        case "up":
            pyautogui.mouseUp(button=button)

    _UiElement.modifier_keys_up_pyautogui(
        pressCtrl=pressCtrl, pressShift=pressShift, pressAlt=pressAlt, pressWin=pressWin
    )

    delay(postExecutionDelay)


@Log.trace()
def move_cursor(
    x: int = 0,
    y: int = 0,
    duration: int = 0,
    relative: bool = True,
    preExecutionDelay: int = 300,
    postExecutionDelay: int = 200,
) -> None:
    """
    Move mouse.

    Parameters:
        x: The x-coordinate or horizontal offset (if relative is True) for the cursor's destination.
        y: The y-coordinate or vertical offset (if relative is True) for the cursor's destination.
        duration: Time to move the mouse to the target position (in seconds). If it is 0, it moves to tatget position immediately.
        relative: If True, the x and y coordinates are treated as offsets from the current cursor position. If False, they are treated as absolute screen coordinates.
        preExecutionDelay: Time to wait before performing the action (in milliseconds).
        postExecutionDelay: Time to wait after performing the action (in milliseconds).
    """
    delay(preExecutionDelay)

    if relative:
        pyautogui.moveTo(x=get_mouse_position()["x"] + x, y=get_mouse_position()["y"] + y, duration=duration)
    else:
        pyautogui.moveTo(x=x, y=y, duration=duration)
    delay(postExecutionDelay)


""" def drag(
    xStart: int = 0,
    yStart: int = 0,
    xEnd: int = 0,
    yEnd: int = 0,
    button: MouseButton= "left",
    pressCtrl: bool = False,
    pressShift: bool = False,
    pressAlt: bool = False,
    pressWin: bool = False,
    duration: int = 0,
    preExecutionDelay: int = 300,
    postExecutionDelay: int = 200,
) -> None: ... """


@Log.trace()
def scroll_wheel(
    times: int = 1,
    direction: Literal["down", "up"] = "down",
    pressCtrl: bool = False,
    pressShift: bool = False,
    pressAlt: bool = False,
    pressWin: bool = False,
    preExecutionDelay: int = 300,
    postExecutionDelay: int = 200,
) -> None:
    """
    Make the mouse scroll down or up.
    
    Parameters:
        times: The number of increments to scroll the wheel.
        direction: The direction to scroll the wheel; valid values are "down" or "up".
        pressCtrl: If True, holds the Ctrl key during the scroll.
        pressShift: If True, holds the Shift key during the scroll.
        pressAlt: If True, holds the Alt key during the scroll.
        pressWin: If True, holds the Windows key during the scroll.
        preExecutionDelay: Time to wait before performing the action (in milliseconds).
        postExecutionDelay: Time to wait after performing the action (in milliseconds).
    """
    if direction not in ["down", "up"]:
        raise ValueError(f"The argument direction({direction}) should be one of {['down', 'up']}")

    delay(preExecutionDelay)

    _UiElement.modifier_keys_down_pyautogui(
        pressCtrl=pressCtrl, pressShift=pressShift, pressAlt=pressAlt, pressWin=pressWin
    )

    match direction:
        case "down":
            for i in range(0, times, 1):
                mouse.scroll(dx=0, dy=-1)
                delay(100)

        case "up":
            for i in range(0, times, 1):
                mouse.scroll(dx=0, dy=1)
                delay(100)

        case _:
            raise ValueError(f"The argument direction({direction}) should be 'down' or 'up'.")

    _UiElement.modifier_keys_up_pyautogui(
        pressCtrl=pressCtrl, pressShift=pressShift, pressAlt=pressAlt, pressWin=pressWin
    )

    delay(postExecutionDelay)


if __name__ == "__main__":
    # from liberrpa._Selector import *
    from time import time

    timeStart = time()

    """ print(selector)
    move_cursor(x=100)
    move_to_element(
        selector=selector,
        timeout=10000,
        preExecutionDelay=300,
        postExecutionDelay=200,
        offsetX=0,
        offsetY=0,
        position="center",
        duration=0,
    ) """

    """ click_element(
        selector=image1,
        offsetX=0,
        offsetY=0,
        button="left",
        clickMode="single_click",
        executionMode="simulate",
        position="center",
        pressCtrl=True,
        pressShift=False,
        pressAlt=False,
        pressWin=False,
        duration=0,
        timeout=10000,
        preExecutionDelay=300,
        postExecutionDelay=200,
    ) """
    """ move_to_element(
        selector=image1,
        timeout=10000,
        preExecutionDelay=300,
        postExecutionDelay=200,
        offsetX=0,
        offsetY=0,
        position="top_left",
        duration=0,
    ) """
    # click(button="left", clickMode="single_click", pressCtrl=False)

    # move_cursor(x=100, y=100, duration=0, relative=False)

    # scroll_wheel(times=2, direction="up", pressCtrl=False)

    # while True:
    #     print(get_mouse_position())

    print("time used:", time() - timeStart)
