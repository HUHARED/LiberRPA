# FileName: Keyboard.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
import liberrpa.UI._UiElement as _UiElement
from liberrpa.Common._TypedValue import (
    ExecutionMode,
    InputKey,
    SelectorWindow,
    SelectorUia,
    SelectorHtml,
)
from liberrpa.UI._TerminableThread import timeout_kill_thread
from liberrpa.Common._Exception import UiOperationError
from liberrpa.Mouse import _get_5_coordinates
from liberrpa.Common._Chrome import set_element_text, focus_element
from liberrpa.Basic import delay

import string
import json
import uiautomation
from pynput.keyboard import Controller, Key
import pyautogui
import ctypes
from typing import Literal

keyboard = Controller()

# Get list from KeyboardKey.
listKeys: list[str] = list(InputKey.__args__)


def _check_keyboard_type_mode(typeMode: str) -> None:
    listValue = ["click", "key_down", "key_up"]
    if typeMode not in listValue:
        raise ValueError(f"The argument typeMode({typeMode}) should be one of {listValue}")


def _check_key(key: str) -> None:
    global listKeys
    if key not in listKeys:
        raise ValueError(f"The argument key({key}) should be one of {listKeys}")


def _simulate_write(text: str, interval: int = 0) -> None:
    # Define all characters that pyautogui can type based on a typical keyboard layout.
    strTypableCharacters = string.ascii_letters + string.digits + string.punctuation + " \t\n"

    # Replace "\r\n" to "\n" for standardizing.
    text = text.replace("\r\n", "\n")

    dictCannotType: dict[int, str] = {}
    for idx, item in enumerate(text, start=0):
        if (item in strTypableCharacters) == False:
            dictCannotType[idx] = item

    if len(dictCannotType.keys()) != 0:
        raise ValueError(
            f"In the argument text, the characters of these position cannot be typed: {json.dumps(dictCannotType,ensure_ascii=False)}"
        )  # Use json instead of str() to show \n, \t, etc.

    # Due to the interval time between type each character is not right, so use the interval argument in pyautogui.write(), so split the original text by '\n'.
    """ for char in text:
        if char == "\n":
            pyautogui.press("enter")
        else:
            pyautogui.write(char)
        sleep(interval / 1000) """

    listTemp = text.split("\n")
    floatInterval = interval / 1000
    for idx, strTemp in enumerate(listTemp, start=0):
        if idx != len(listTemp) - 1:
            pyautogui.write(strTemp, interval=floatInterval)
            pyautogui.press("enter", interval=floatInterval)
        elif idx == len(listTemp) - 1 and strTemp != "":
            pyautogui.write(strTemp, interval=floatInterval)
        else:
            # idx==len(listTemp) - 1 and strTemp == "":
            # The previous one has type Enter, so it doesn't need to do.
            pass


def _write_text(
    text: str,
    executionMode: ExecutionMode = "api",
    preExecutionDelay: int = 300,
    postExecutionDelay: int = 200,
) -> None:

    _UiElement.check_execution_type(executionMode=executionMode)

    delay(preExecutionDelay)

    match executionMode:
        case "api":
            # When use IME(Input Method Editor) or opening Capslock, the written text may be incorrect. So close Capslock if it's opening.
            boolCapslockChanged = False
            if ctypes.windll.user32.GetKeyState(0x14) == 1:
                # NOTE: Use press&release(pynput) instead of type() due to type() need a char instead of Key.caps_lock
                keyboard.press(Key.caps_lock)
                keyboard.release(Key.caps_lock)
                boolCapslockChanged = True

            for char in text:
                if char == "\n":
                    keyboard.press(Key.enter)
                    keyboard.release(Key.enter)
                elif char == "\t":
                    keyboard.press(Key.tab)
                    keyboard.release(Key.tab)
                else:
                    try:
                        keyboard.type(char)
                    except Exception as e:
                        # Change CapsLock back.
                        keyboard.press(Key.caps_lock)
                        keyboard.release(Key.caps_lock)
                        raise UiOperationError(f"Error when type '{char}', error: {e}")
            # Change CapsLock back.
            if boolCapslockChanged == True:
                keyboard.press(Key.caps_lock)
                keyboard.release(Key.caps_lock)

        case "simulate":
            _simulate_write(text=text, interval=0)

    delay(postExecutionDelay)


@Log.trace()
def write_text(
    text: str,
    executionMode: ExecutionMode = "api",
    timeout: int = 10000,
    preExecutionDelay: int = 300,
    postExecutionDelay: int = 200,
) -> None:
    """
    Write text in the current element focused.

    Parameters:
        text: The text to be written.
        executionMode: Options are "simulate" and "api". "simulate" may be affected by IME(Input Method Editor) or Capslock but "api" will not, and "uia" supports more characters.
        timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the function doesn't completed after "timeout", it will throw an UiTimeoutError.
        preExecutionDelay: Time to wait before performing the action (in milliseconds).
        postExecutionDelay: Time to wait after performing the action (in milliseconds).
    """
    timeout = _UiElement.check_set_timeout(timeout=timeout)

    return timeout_kill_thread(timeout=timeout)(_write_text)(
        text,
        executionMode,
        preExecutionDelay,
        postExecutionDelay,
    )


def _write_text_into_element(
    selector: SelectorWindow | SelectorUia | SelectorHtml,
    text: str,
    executionMode: ExecutionMode = "api",
    interval: int = 10,
    emptyOriginalText: bool = False,
    validateWrittenText: bool = False,
    timeout: int = 10000,
    preExecutionDelay: int = 300,
    postExecutionDelay: int = 200,
) -> None:
    _UiElement.check_execution_type(executionMode=executionMode)

    if selector.get("category") == "image":
        raise UiOperationError(f"Not support writing text into an image element.")

    if selector.get("category") == "html" and executionMode == "simulate" and validateWrittenText:
        # Even html element can get text, but its logic in here is too complex, take more time, so don't do it.
        raise UiOperationError("Not support validating text to an html element by simuate mode.")

    if selector.get("category") == "html" and executionMode == "api":
        _UiElement.activate_element_window(selector=selector)
        set_element_text(
            htmlSelector=selector["specification"],  # type: ignore - it's SelectorHtml
            text=text,
            emptyOriginalText=emptyOriginalText,
            validateWrittenText=validateWrittenText,
            preExecutionDelay=preExecutionDelay,
            timeout=timeout,
        )
        delay(postExecutionDelay)
        return None

    uiTarget, dictTarget = _UiElement.get_element_with_pre_delay(selector=selector, preExecutionDelay=preExecutionDelay)

    match executionMode:
        case "api":
            if isinstance(uiTarget, uiautomation.Control):
                pattern = uiTarget.GetPattern(uiautomation.PatternId.ValuePattern)
                if pattern:
                    if emptyOriginalText == True:
                        pattern.SetValue(text)
                    else:
                        pattern.SetValue(pattern.Value + text)

                    if validateWrittenText:
                        if pattern.Value != text:
                            raise ValueError(
                                f"The written text ({json.dumps(pattern.Value,ensure_ascii=False)}) is not equals with the argument text({json.dumps(text,ensure_ascii=False)}."
                            )  # Use json instead of str() to show \n, \t, etc.
                    delay(postExecutionDelay)
                    return None
                else:
                    raise ValueError(
                        "The element doesn't support the argument executionMode('api'). selector: {selector}"
                    )
            else:
                # html or image element api write
                raise UiOperationError(
                    "(!!!It should not appear.) Use api mode for html or image element should have be handle!!! selector: {selector}"
                )

        case "simulate":
            # If use simulate type, must click it before writing.
            dictcoordinates = _get_5_coordinates(dictAttr=dictTarget)
            pyautogui.moveTo(x=dictcoordinates["center"][0], y=dictcoordinates["center"][1])
            pyautogui.click()

            if emptyOriginalText:
                # The simulate type to empty text.
                pyautogui.hotkey("ctrl", "a")
                pyautogui.press("backspace")
            else:
                # If didn't need to empty orginal text, type Ctrl+End to move to end.
                pyautogui.hotkey("ctrl", "end")

            _simulate_write(text=text, interval=interval)

            if validateWrittenText:
                if isinstance(uiTarget, uiautomation.Control):
                    strWrittenText: str | None = None
                    # Try to retrieve text using ValuePattern if available
                    pattern = uiTarget.GetPattern(uiautomation.PatternId.ValuePattern)
                    if pattern and pattern.Value:
                        strWrittenText = pattern.Value
                    else:
                        # If ValuePattern is not available or provides no text, check TextPattern
                        pattern = uiTarget.GetPattern(uiautomation.PatternId.TextPattern)
                        if pattern:
                            strText = pattern.DocumentRange.GetText(-1)
                            if strText:
                                strWrittenText = strText
                    if strWrittenText is None:
                        raise ValueError(
                            f"The element doesn't support getting text for validation. selector: {selector}"
                        )

                    strWrittenTextTemp = strWrittenText.replace("\r\n", "\n")
                    textTemp = text.replace("\r\n", "\n")

                    if strWrittenTextTemp != textTemp:
                        # Due to pyautogui use Enter to input '\n', it may become '\r\n', so replace it.
                        raise ValueError(
                            f"The written text ({json.dumps(strWrittenText,ensure_ascii=False)}) is not equals with the argument text({json.dumps(text,ensure_ascii=False)})."
                        )  # Use json instead of str() to show \n, \t, etc.
                else:
                    # html or image element simulate validate
                    raise UiOperationError(
                        "(!!!It should not appear.) Use simulate mode for html or image element should have be handle!!! selector: {selector}"
                    )
            delay(postExecutionDelay)
            return None

    raise UiOperationError(
        f"The element doesn't support setting text or LiberRPA doesn't have permission. selector: {selector}"
    )


@Log.trace()
def write_text_into_element(
    selector: SelectorWindow | SelectorUia | SelectorHtml,
    text: str,
    executionMode: ExecutionMode = "api",
    interval: int = 10,
    emptyOriginalText: bool = False,
    validateWrittenText: bool = False,
    timeout: int = 10000,
    preExecutionDelay: int = 300,
    postExecutionDelay: int = 200,
) -> None:
    """
    Focus an element then write text into it.

    Parameters:
        selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
        text: The text to be written.
        executionMode: Options are "simulate" and "api". "simulate" may be affected by IME(Input Method Editor) or Capslock but "api" will not, and "uia" supports more characters.
        interval: the interval time(milliseconds) between type each character. Only works in "simulate" mode.
        emptyOriginalText: Whether delete existing text(by typing ctrl+a and backspace).
        validateWrittenText: Whether check the typed text, not support html element's simulate mode.
        timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the function doesn't completed after "timeout", it will throw an UiTimeoutError.
        preExecutionDelay: Time to wait before performing the action (in milliseconds).
        postExecutionDelay: Time to wait after performing the action (in milliseconds).
    """
    timeout = _UiElement.check_set_timeout(timeout=timeout)

    return timeout_kill_thread(timeout=timeout)(_write_text_into_element)(
        selector,
        text,
        executionMode,
        interval,
        emptyOriginalText,
        validateWrittenText,
        timeout,
        preExecutionDelay,
        postExecutionDelay,
    )


def _type_key_in_element(
    selector: SelectorWindow | SelectorUia | SelectorHtml,
    key: InputKey = "enter",
    pressCtrl: bool = False,
    pressShift: bool = False,
    pressAlt: bool = False,
    pressWin: bool = False,
    timeout: int = 10000,
    preExecutionDelay: int = 300,
    postExecutionDelay: int = 200,
) -> None:

    _check_key(key=key)

    if selector.get("category") == "image":
        raise UiOperationError(f"Not support typing key in an image element.")

    if selector.get("category") == "html":
        _UiElement.activate_element_window(selector=selector)
        focus_element(
            htmlSelector=selector["specification"],  # type: ignore - it's SelectorHtml
            preExecutionDelay=preExecutionDelay,
            timeout=timeout,
        )
        _UiElement.modifier_keys_down_pyautogui(
            pressCtrl=pressCtrl, pressShift=pressShift, pressAlt=pressAlt, pressWin=pressWin
        )
        pyautogui.press(key)
        _UiElement.modifier_keys_up_pyautogui(
            pressCtrl=pressCtrl, pressShift=pressShift, pressAlt=pressAlt, pressWin=pressWin
        )
    else:
        # uia
        uiTarget, _ = _UiElement.get_element_with_pre_delay(selector=selector, preExecutionDelay=preExecutionDelay)
        if isinstance(uiTarget, uiautomation.Control):
            # Use pyautogui, must focus it first.
            uiTarget.SetFocus()

        _UiElement.modifier_keys_down_pyautogui(
            pressCtrl=pressCtrl, pressShift=pressShift, pressAlt=pressAlt, pressWin=pressWin
        )
        pyautogui.press(key)
        _UiElement.modifier_keys_up_pyautogui(
            pressCtrl=pressCtrl, pressShift=pressShift, pressAlt=pressAlt, pressWin=pressWin
        )

    delay(postExecutionDelay)


@Log.trace()
def type_key_in_element(
    selector: SelectorWindow | SelectorUia | SelectorHtml,
    key: InputKey = "enter",
    pressCtrl: bool = False,
    pressShift: bool = False,
    pressAlt: bool = False,
    pressWin: bool = False,
    timeout: int = 10000,
    preExecutionDelay: int = 300,
    postExecutionDelay: int = 200,
) -> None:
    """
    Focus an element then type a key.

    Parameters:
        selector: The dictionary for locating an element, it is generated by UI Analyzer, you can modify it to make it more concise, more suitable for all situations.
        key: The key to be typed, all supported key in the type InputKey: ['enter', 'esc', 'tab', 'space', 'backspace', 'up', 'down', 'left', 'right', 'delete', 'insert', 'home', 'end', 'pageup', 'pagedown', 'capslock', 'numlock', 'printscreen', 'scrolllock', 'pause', 'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'num0', 'num1', 'num2', 'num3', 'num4', 'num5', 'num6', 'num7', 'num8', 'num9', 'add', 'subtract', 'multiply', 'divide', 'decimal', 'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12', 'f13', 'f14', 'f15', 'f16', 'f17', 'f18', 'f19', 'f20', 'f21', 'f22', 'f23', 'f24', '`', '~', '!', '@', '#', '$', '%', '^', '&', '*', '(', ')', '-', '_', '=', '+', '[', '{', ']', '}', '\\\\', '|', ';', ':', "'", '"', ',', '<', '.', '>', '/', '?', 'shift', 'shiftleft', 'shiftright', 'ctrl', 'ctrlleft', 'ctrlright', 'alt', 'altleft', 'altright', 'win', 'winleft', 'winright', 'volumemute', 'volumedown', 'volumeup', 'playpause', 'stop', 'nexttrack', 'prevtrack', 'browserback', 'browserfavorites', 'browserforward', 'browserhome', 'browserrefresh', 'browsersearch', 'browserstop'] (2 backslash is not visual in Pylance, so use 4 backslash to express one visual backslash)
        pressCtrl: If True, holds the Ctrl key during the type.
        pressShift: If True, holds the Shift key during the type.
        pressAlt: If True, holds the Alt key during the type.
        pressWin: If True, holds the Windows key during the type.
        timeout: Maximum time allowed for the function to complete (in milliseconds). If timeout < 3000 (milliseconds), it will be set to 3000. If the function doesn't completed after "timeout", it will throw an UiTimeoutError.
        preExecutionDelay: Time to wait before performing the action (in milliseconds).
        postExecutionDelay: Time to wait after performing the action (in milliseconds).
    """

    timeout = _UiElement.check_set_timeout(timeout=timeout)

    return timeout_kill_thread(timeout=timeout)(_type_key_in_element)(
        selector,
        key,
        pressCtrl,
        pressShift,
        pressAlt,
        pressWin,
        timeout,
        preExecutionDelay,
        postExecutionDelay,
    )


@Log.trace()
def type_key(
    key: InputKey = "enter",
    typeMode: Literal["click", "key_down", "key_up"] = "click",
    pressCtrl: bool = False,
    pressShift: bool = False,
    pressAlt: bool = False,
    pressWin: bool = False,
    preExecutionDelay: int = 300,
    postExecutionDelay: int = 200,
) -> None:
    """
    Type a key in the current element focused.

    Parameters:
        key: The key to be typed, all supported key in the type InputKey: ['enter', 'esc', 'tab', 'space', 'backspace', 'up', 'down', 'left', 'right', 'delete', 'insert', 'home', 'end', 'pageup', 'pagedown', 'capslock', 'numlock', 'printscreen', 'scrolllock', 'pause', 'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'num0', 'num1', 'num2', 'num3', 'num4', 'num5', 'num6', 'num7', 'num8', 'num9', 'add', 'subtract', 'multiply', 'divide', 'decimal', 'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12', 'f13', 'f14', 'f15', 'f16', 'f17', 'f18', 'f19', 'f20', 'f21', 'f22', 'f23', 'f24', '`', '~', '!', '@', '#', '$', '%', '^', '&', '*', '(', ')', '-', '_', '=', '+', '[', '{', ']', '}', '\\\\', '|', ';', ':', "'", '"', ',', '<', '.', '>', '/', '?', 'shift', 'shiftleft', 'shiftright', 'ctrl', 'ctrlleft', 'ctrlright', 'alt', 'altleft', 'altright', 'win', 'winleft', 'winright', 'volumemute', 'volumedown', 'volumeup', 'playpause', 'stop', 'nexttrack', 'prevtrack', 'browserback', 'browserfavorites', 'browserforward', 'browserhome', 'browserrefresh', 'browsersearch', 'browserstop'] (2 backslash is not visual in Pylance, so use 4 backslash to express one visual backslash)
        typeMode: The type of keyboard action to perform. Options are:
            "click" for a single press and release,
            "key_down" for pressing the key down,
            "key_up" for releasing a pressed key.
        pressCtrl: If True, holds the Ctrl key during the type.
        pressShift: If True, holds the Shift key during the type.
        pressAlt: If True, holds the Alt key during the type.
        pressWin: If True, holds the Windows key during the type.
        preExecutionDelay: Time to wait before performing the action (in milliseconds).
        postExecutionDelay: Time to wait after performing the action (in milliseconds).
    """

    _check_key(key=key)
    _check_keyboard_type_mode(typeMode=typeMode)

    delay(preExecutionDelay)

    _UiElement.modifier_keys_down_pyautogui(
        pressCtrl=pressCtrl, pressShift=pressShift, pressAlt=pressAlt, pressWin=pressWin
    )

    match typeMode:
        case "click":
            pyautogui.press(key)
        case "key_down":
            pyautogui.keyDown(key)
        case "key_up":
            pyautogui.keyUp(key)
        case _:
            raise ValueError(f"The argument state({typeMode}) should be one of {['click', 'key_down', 'key_up']}")

    _UiElement.modifier_keys_up_pyautogui(
        pressCtrl=pressCtrl, pressShift=pressShift, pressAlt=pressAlt, pressWin=pressWin
    )

    delay(postExecutionDelay)
    return None


if __name__ == "__main__":
    # from liberrpa._Selector import *
    from time import time

    timeStart = time()

    text = "1234567890こんにちは世界-=,./!@#$%^&*()ÄäÖöÜü中文字符✔\nEnter\r\nNewLine\tTab\nÄäÖöÜü\n中文字符✔🤷😊Emoji：こんにちは世界"
    # text = "1234567890こんにちは世界-=,./!@#$%^&*()\nEnter\rNewLine\tTab\nÄäÖöÜü\n中文字符✔Emoji：こんにちは世界"
    # text = "123123abclkjaf1024uag123123\t44\r\n44"
    # text = "\nHello, how are\n you today?\n"
    # text = "\nHello. How are\n you today?" * 100
    # write_text(text=text, executionMode="api", timeout=3000, preExecutionDelay=2000, postExecutionDelay=200)
    """ write_text_into_element(
        selector=selector,
        text=text,
        executionMode="api",
        interval=10,
        emptyOriginalText=True,
        validateWrittenText=False,
        timeout=10000,
        preExecutionDelay=2000,
        postExecutionDelay=200,
    ) """

    """ for key in ["a", "b"]:
        print(f"==={key}===")
        # type_key_in_element(selector=selector, key=key, pressCtrl=False, pressAlt=False, pressShift=False, pressWin=False, preExecutionDelay=1000, postExecutionDelay=200)
        type_key(key=key, typeMode="click", pressCtrl=True, pressAlt=False, pressShift=False, pressWin=False, preExecutionDelay=1000, postExecutionDelay=200)  # type: ignore
        type_key(key=key, typeMode="key_down", pressCtrl=False, pressAlt=False, pressShift=True, pressWin=False, preExecutionDelay=1000, postExecutionDelay=200)  # type: ignore
        type_key(key=key, typeMode="key_up", pressCtrl=False, pressAlt=False, pressShift=True, pressWin=False, preExecutionDelay=1000, postExecutionDelay=200)  # type: ignore """

    """ write_text_into_element(
        selector=image1,
        text="123",
        executionMode="api",
        interval=10,
        emptyOriginalText=False,
        validateWrittenText=False,
        timeout=10000,
        preExecutionDelay=300,
        postExecutionDelay=200,
    ) """

    # type_key_in_element(selector=image1, key="c", pressCtrl=True)
    print("time used:", time() - timeStart)
