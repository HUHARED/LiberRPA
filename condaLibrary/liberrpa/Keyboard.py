# FileName: Keyboard.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
import liberrpa.UI._UiElement as _UiElement
from liberrpa.Common._TypedValue import ExecutionMode, InputKey
from liberrpa.UI._UiDict import SelectorWindow, SelectorUia, SelectorHtml
from liberrpa.UI._TerminableThread import timeout_kill_thread
from liberrpa.UI._OperationLock import lock_ui_operation
from liberrpa.UI._SelectorValidation import as_selector_html
from liberrpa.Common._Exception import UiOperationError
from liberrpa.Mouse import _get_5_coordinates
from liberrpa.Common._Chrome import set_element_text, focus_element
from liberrpa.Basic import delay

import string
import json
import uiautomation
from pynput.keyboard import Controller, Key
import pyautogui

pyautogui.FAILSAFE = False  # Allow clicking screen corners
import ctypes
from typing import Literal, cast

_keyboard = Controller()

# Get list from KeyboardKey.
_LIST_INPUT_KEYS: list[str] = list(InputKey.__args__)


def _check_keyboard_type_mode(typeMode: str) -> None:
    listValue = ["click", "key_down", "key_up"]
    if typeMode not in listValue:
        raise ValueError(f"The argument typeMode({typeMode}) should be one of {listValue}")


def _check_key(key: str) -> None:
    global _LIST_INPUT_KEYS
    if key not in _LIST_INPUT_KEYS:
        raise ValueError(f"The argument key({key}) should be one of {_LIST_INPUT_KEYS}")


def _simulate_write(text: str, interval: int = 0) -> None:
    # Define all characters that pyautogui can type based on a typical keyboard layout.
    strTypableCharacters = string.ascii_letters + string.digits + string.punctuation + " \t\n"

    # Replace "\r\n" to "\n" for standardizing.
    text = text.replace("\r\n", "\n")

    dictCannotType: dict[int, str] = {}
    for idx, item in enumerate(text, start=0):
        if item not in strTypableCharacters:
            dictCannotType[idx] = item

    if len(dictCannotType.keys()) != 0:
        raise ValueError(
            f"In the argument text, the characters of these position cannot be typed: {json.dumps(dictCannotType, ensure_ascii=False)}"
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
            if ctypes.windll.user32.GetKeyState(0x14) & 1:
                # NOTE: Use press&release(pynput) instead of type() due to type() need a char instead of Key.caps_lock
                _keyboard.press(Key.caps_lock)
                _keyboard.release(Key.caps_lock)
                boolCapslockChanged = True

            try:
                for char in text:
                    if char == "\n":
                        _keyboard.press(Key.enter)
                        _keyboard.release(Key.enter)
                    elif char == "\t":
                        _keyboard.press(Key.tab)
                        _keyboard.release(Key.tab)
                    else:
                        try:
                            _keyboard.type(char)
                        except Exception as e:
                            raise UiOperationError(f"Error when type '{char}', error: {e}")
            finally:
                # Change CapsLock back.
                if boolCapslockChanged:
                    _keyboard.press(Key.caps_lock)
                    _keyboard.release(Key.caps_lock)

        case "simulate":
            _simulate_write(text=text, interval=0)

    delay(postExecutionDelay)


@Log.trace()
@lock_ui_operation
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
        executionMode: Options are "simulate" and "api". "simulate" may be affected by IME(Input Method Editor) or CapsLock, while "api" can input more characters more reliably.
        timeout: Maximum time allowed for normal completion, in milliseconds. Values below 3000 are treated as 3000. The actual elapsed time may be longer if LiberRPA enters its hard-timeout fallback before raising a timeout-related exception.
        preExecutionDelay: Time to wait before performing the action, in milliseconds.
        postExecutionDelay: Time to wait after performing the action, in milliseconds.
    """
    timeout = _UiElement.check_set_timeout(timeout=timeout)

    return timeout_kill_thread(timeout=timeout)(_write_text)(
        text,
        executionMode,
        preExecutionDelay,
        postExecutionDelay,
    )


def _normalize_written_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _get_uia_control_text(control: uiautomation.Control) -> str | None:
    pattern = cast(
        uiautomation.ValuePattern | None,
        control.GetPattern(uiautomation.PatternId.ValuePattern),
    )
    if pattern is not None:
        value = pattern.Value
        if value is None:
            return ""
        return str(value)

    pattern = cast(
        uiautomation.TextPattern | None,
        control.GetPattern(uiautomation.PatternId.TextPattern),
    )
    if pattern is not None:
        text = pattern.DocumentRange.GetText(-1)
        if text is None:
            return ""
        return str(text)

    return None


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
        raise UiOperationError("Not support writing text into an image element.")

    if selector.get("category") == "html" and executionMode == "simulate" and validateWrittenText:
        # Even html element can get text, but its logic here is too complex and takes more time.
        raise UiOperationError("Not support validating text to an html element by simulate mode.")

    if selector.get("category") == "html" and executionMode == "api":
        _UiElement.activate_element_window(selector=selector)
        set_element_text(
            htmlSelector=as_selector_html(selector=selector)["specification"],
            text=text,
            emptyOriginalText=emptyOriginalText,
            validateWrittenText=validateWrittenText,
            preExecutionDelay=preExecutionDelay,
            timeout=timeout,
        )
        delay(postExecutionDelay)
        return None

    uiTarget, dictTarget = _UiElement.get_element_with_pre_delay(
        selector=selector,
        preExecutionDelay=preExecutionDelay,
    )

    match executionMode:
        case "api":
            if not isinstance(uiTarget, uiautomation.Control):
                # html api mode has already been handled above. image is not supported.
                raise UiOperationError(
                    f"(!!!It should not appear.) API mode for html or image element should have been handled. "
                    f"selector: {selector}"
                )

            pattern = cast(
                uiautomation.ValuePattern | None,
                uiTarget.GetPattern(uiautomation.PatternId.ValuePattern),
            )
            if pattern is None:
                raise ValueError(
                    f"The element does not support the argument executionMode('api'). selector: {selector}"
                )

            strOldText = "" if pattern.Value is None else str(pattern.Value)
            strTargetText = text if emptyOriginalText else strOldText + text

            if not pattern.SetValue(strTargetText):
                raise UiOperationError(f"Failed to set text by ValuePattern. selector: {selector}")

            if validateWrittenText:
                strWrittenText = "" if pattern.Value is None else str(pattern.Value)

                if _normalize_written_text(strWrittenText) != _normalize_written_text(strTargetText):
                    raise ValueError(
                        f"The written text ({json.dumps(strWrittenText, ensure_ascii=False)}) is not equal to the expected text ({json.dumps(strTargetText, ensure_ascii=False)})."
                    )

            delay(postExecutionDelay)
            return None

        case "simulate":

            def _write_by_simulation() -> None:
                # If use simulate type, must click it before writing.
                dictCoordinates = _get_5_coordinates(dictAttr=dictTarget)
                pyautogui.moveTo(x=dictCoordinates["center"][0], y=dictCoordinates["center"][1])
                pyautogui.click()

                if emptyOriginalText:
                    # The simulate type to empty text.
                    pyautogui.hotkey("ctrl", "a")
                    pyautogui.press("backspace")
                else:
                    # If didn't need to empty original text, type Ctrl+End to move to end.
                    pyautogui.hotkey("ctrl", "end")

                _simulate_write(text=text, interval=interval)

            if validateWrittenText:
                if not isinstance(uiTarget, uiautomation.Control):
                    raise UiOperationError(
                        f"(!!!It should not appear.) Simulate mode for html or image element should have been handled. "
                        f"selector: {selector}"
                    )

                if emptyOriginalText:
                    strExpectedText = text
                else:
                    strOldText = _get_uia_control_text(control=uiTarget)
                    if strOldText is None:
                        raise ValueError(
                            f"The element does not support getting original text for validation. selector: {selector}"
                        )
                    strExpectedText = strOldText + text

                _write_by_simulation()

                strWrittenText = _get_uia_control_text(control=uiTarget)
                if strWrittenText is None:
                    raise ValueError(f"The element does not support getting text for validation. selector: {selector}")

                if _normalize_written_text(strWrittenText) != _normalize_written_text(strExpectedText):
                    raise ValueError(
                        f"The written text ({json.dumps(strWrittenText, ensure_ascii=False)}) "
                        f"is not equal to the expected text "
                        f"({json.dumps(strExpectedText, ensure_ascii=False)})."
                    )

            else:
                _write_by_simulation()

            delay(postExecutionDelay)
            return None

    raise UiOperationError(
        f"The element does not support setting text or LiberRPA does not have permission. selector: {selector}"
    )


@Log.trace()
@lock_ui_operation
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
        selector: A selector dictionary generated by UI Analyzer for locating an element. You can edit it to make it more concise or more robust in different situations.
        text: The text to be written.
        executionMode: Options are "simulate" and "api". "simulate" may be affected by IME(Input Method Editor) or CapsLock, while "api" can input more characters more reliably.
        interval: the interval time(milliseconds) between type each character. Only works in "simulate" mode.
        emptyOriginalText: Whether delete existing text(by typing ctrl+a and backspace).
        validateWrittenText: Whether check the typed text, not support html element's simulate mode.
        timeout: Maximum time allowed for normal completion, in milliseconds. Values below 3000 are treated as 3000. The actual elapsed time may be longer if LiberRPA enters its hard-timeout fallback before raising a timeout-related exception.
        preExecutionDelay: Time to wait before performing the action, in milliseconds.
        postExecutionDelay: Time to wait after performing the action, in milliseconds.
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
        raise UiOperationError("Not support typing key in an image element.")

    if selector.get("category") == "html":
        _UiElement.activate_element_window(selector=selector)
        focus_element(
            htmlSelector=as_selector_html(selector=selector)["specification"],
            preExecutionDelay=preExecutionDelay,
            timeout=timeout,
        )

        with _UiElement.holding_modifier_keys(
            pressCtrl=pressCtrl,
            pressShift=pressShift,
            pressAlt=pressAlt,
            pressWin=pressWin,
        ):
            pyautogui.press(key)

    else:
        # uia
        uiTarget, _ = _UiElement.get_element_with_pre_delay(selector=selector, preExecutionDelay=preExecutionDelay)
        if isinstance(uiTarget, uiautomation.Control):
            # Use pyautogui, must focus it first.
            uiTarget.SetFocus()

        with _UiElement.holding_modifier_keys(
            pressCtrl=pressCtrl,
            pressShift=pressShift,
            pressAlt=pressAlt,
            pressWin=pressWin,
        ):
            pyautogui.press(key)

    delay(postExecutionDelay)


@Log.trace()
@lock_ui_operation
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
        selector: A selector dictionary generated by UI Analyzer for locating an element. You can edit it to make it more concise or more robust in different situations.
        key: The key to be typed, all supported key in the type InputKey: ['enter', 'esc', 'tab', 'space', 'backspace', 'up', 'down', 'left', 'right', 'delete', 'insert', 'home', 'end', 'pageup', 'pagedown', 'capslock', 'numlock', 'printscreen', 'scrolllock', 'pause', 'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'num0', 'num1', 'num2', 'num3', 'num4', 'num5', 'num6', 'num7', 'num8', 'num9', 'add', 'subtract', 'multiply', 'divide', 'decimal', 'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12', 'f13', 'f14', 'f15', 'f16', 'f17', 'f18', 'f19', 'f20', 'f21', 'f22', 'f23', 'f24', '`', '~', '!', '@', '#', '$', '%', '^', '&', '*', '(', ')', '-', '_', '=', '+', '[', '{', ']', '}', '\\\\', '|', ';', ':', "'", '"', ',', '<', '.', '>', '/', '?', 'shift', 'shiftleft', 'shiftright', 'ctrl', 'ctrlleft', 'ctrlright', 'alt', 'altleft', 'altright', 'win', 'winleft', 'winright', 'volumemute', 'volumedown', 'volumeup', 'playpause', 'stop', 'nexttrack', 'prevtrack', 'browserback', 'browserfavorites', 'browserforward', 'browserhome', 'browserrefresh', 'browsersearch', 'browserstop'] (2 backslash is not visual in Pylance, so use 4 backslash to express one visual backslash)
        pressCtrl: If True, holds the Ctrl key during the type.
        pressShift: If True, holds the Shift key during the type.
        pressAlt: If True, holds the Alt key during the type.
        pressWin: If True, holds the Windows key during the type.
        timeout: Maximum time allowed for normal completion, in milliseconds. Values below 3000 are treated as 3000. The actual elapsed time may be longer if LiberRPA enters its hard-timeout fallback before raising a timeout-related exception.
        preExecutionDelay: Time to wait before performing the action, in milliseconds.
        postExecutionDelay: Time to wait after performing the action, in milliseconds.
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
@lock_ui_operation
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
        pressCtrl: If True, holds the Ctrl key while pressing the key. Only supports typeMode='click'.
        pressShift: If True, holds the Shift key while pressing the key. Only supports typeMode='click'.
        pressAlt: If True, holds the Alt key while pressing the key. Only supports typeMode='click'.
        pressWin: If True, holds the Windows key while pressing the key. Only supports typeMode='click'.
        preExecutionDelay: Time to wait before performing the action, in milliseconds.
        postExecutionDelay: Time to wait after performing the action, in milliseconds.
    """

    _check_key(key=key)
    _check_keyboard_type_mode(typeMode=typeMode)

    if typeMode != "click" and any((pressCtrl, pressShift, pressAlt, pressWin)):
        raise ValueError(
            "pressCtrl/pressShift/pressAlt/pressWin only support typeMode='click'. For key_down/key_up, call type_key() for modifier keys explicitly."
        )

    delay(preExecutionDelay)

    match typeMode:
        case "click":
            with _UiElement.holding_modifier_keys(
                pressCtrl=pressCtrl,
                pressShift=pressShift,
                pressAlt=pressAlt,
                pressWin=pressWin,
            ):
                pyautogui.press(key)
        case "key_down":
            pyautogui.keyDown(key)
        case "key_up":
            pyautogui.keyUp(key)
        case _:
            raise ValueError(f"The argument typeMode({typeMode}) should be one of {['click', 'key_down', 'key_up']}")

    delay(postExecutionDelay)
    return None


if __name__ == "__main__":
    # from ..test._Selector import SlctNotepad2
    from time import monotonic

    timeStart = monotonic()

    SlctNotepad2 = {
        "window": {
            "ProcessName": "notepad.exe",
            "FrameworkId": "Win32",
            "ControlTypeName": "WindowControl",
            "Name": "New Text Document.txt - Notepad",
            "ClassName": "Notepad",
        },
        "category": "uia",
        "specification": [{"ControlTypeName": "EditControl", "Name": "Text Editor", "ClassName": "Edit"}],
    }

    text = "1234567890こんにちは世界-=,./!@#$%^&*()ÄäÖöÜü中文字符✔\nEnter\r\nNewLine\tTab\nÄäÖöÜü\n中文字符✔🤷😊Emoji：こんにちは世界"
    # text = "1234567890こんにちは世界-=,./!@#$%^&*()\nEnter\rNewLine\tTab\nÄäÖöÜü\n中文字符✔Emoji：こんにちは世界"
    # text = "123123abclkjaf1024uag123123\t44\r\n44"
    # text = "\nHello, how are\n you today?\n"
    # text = "\nHello. How are\n you today?" * 100
    write_text(text=text, executionMode="api", timeout=3000, preExecutionDelay=2000, postExecutionDelay=200)
    """ write_text_into_element(
        selector=SlctNotepad2,
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
        type_key(key=key, typeMode="click", pressCtrl=True, pressAlt=False, pressShift=False, pressWin=False, preExecutionDelay=1000, postExecutionDelay=200)
        type_key(key=key, typeMode="key_down", pressCtrl=False, pressAlt=False, pressShift=True, pressWin=False, preExecutionDelay=1000, postExecutionDelay=200)
        type_key(key=key, typeMode="key_up", pressCtrl=False, pressAlt=False, pressShift=True, pressWin=False, preExecutionDelay=1000, postExecutionDelay=200) """

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
    print("time used:", monotonic() - timeStart)
