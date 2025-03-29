# FileName: Trigger.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Dialog import show_notification
from liberrpa.Common._TypedValue import MouseButton, HookKey
import liberrpa.FlowControl.End as End

from pynput.mouse import Button, Listener as MouseListener
import keyboard
import threading
import multiprocessing
import os
import sys
from typing import Any, Literal, Callable, TypeVar

T = TypeVar("T")

dictModifierState = {"ctrl": False, "shift": False, "alt": False, "win": False}


def _check_timing(timing: str) -> None:
    listValue = ["on_press", "on_release"]
    if timing not in listValue:
        raise ValueError(f"The argument timing({timing}) should be one of {listValue}")


def _generate_addition(
    pressCtrl: bool,
    pressShift: bool,
    pressAlt: bool,
    pressWin: bool,
) -> str:
    strAddition = ""
    if pressCtrl:
        strAddition += "Ctrl+"
    if pressShift:
        strAddition += "Shift+"
    if pressAlt:
        strAddition += "Alt+"
    if pressWin:
        strAddition += "Win+"
    return strAddition


def _get_keyname_and_press(event: keyboard.KeyboardEvent) -> tuple[str, bool]:
    # It may be upper English chracter, so use lower()
    strKeyName = event.name.lower() if event.name else None
    if strKeyName is None:
        raise ValueError("Unknown key pressed.")
    strDirection = "press" if event.event_type == "down" else "release"
    boolPressed = True if strDirection == "press" else False
    Log.debug(f"Keyboard Event: {strKeyName} - {strDirection}")

    if strKeyName in {"ctrl", "left ctrl", "right ctrl"}:
        dictModifierState["ctrl"] = boolPressed
    elif strKeyName in {"shift", "left shift", "right shift"}:
        dictModifierState["shift"] = boolPressed
    elif strKeyName in {"alt", "left alt", "right alt"}:
        dictModifierState["alt"] = boolPressed
    elif strKeyName in {"windows", "left windows", "right windows"}:
        dictModifierState["win"] = boolPressed

    return (strKeyName, boolPressed)


def _check_modifiers(
    pressCtrl: bool,
    pressShift: bool,
    pressAlt: bool,
    pressWin: bool,
) -> bool:
    return (
        dictModifierState["ctrl"] == pressCtrl
        and dictModifierState["shift"] == pressShift
        and dictModifierState["alt"] == pressAlt
        and dictModifierState["win"] == pressWin
    )


@Log.trace()
def mouse_trigger(
    func: Callable[..., T],
    args: list[Any] = [],
    button: MouseButton = "left",
    pressCtrl: bool = False,
    pressShift: bool = False,
    pressAlt: bool = False,
    pressWin: bool = False,
    timing: Literal["on_press", "on_release"] = "on_release",
    showNotification: bool = True,
    block: bool = True,
) -> T | None:
    """
    Trigger a specified function when the given mouse button and modifier keys are pressed/released.

    Parameters:
        func: The function to execute when the trigger is activated.
        args: Arguments to pass to the function.
        button: Mouse button to listen for ("left", "right", "middle").
        pressCtrl: Whether the Ctrl key must be pressed.
        pressShift: Whether the Shift key must be pressed.
        pressAlt: Whether the Alt key must be pressed.
        pressWin: Whether the Win key must be pressed.
        timing: When to trigger the function, "on_press" or "on_release".
        showNotification: Whether to show a notification when the function is triggered.
        block: Whether to block the main thread until the trigger is executed.

    Returns:
        T|None: The return value of the executed function if block=True, or None otherwise.
    """
    listValue = ["left", "right", "middle"]
    if button not in listValue:
        raise ValueError(f"The argument button({button}) should be one of {listValue}")

    _check_timing(timing=timing)

    dictResult: dict[str, T | None] = {"result": None}
    eventStop = threading.Event()

    def on_key_event_for_mouse(event: keyboard.KeyboardEvent) -> None:
        _get_keyname_and_press(event=event)

    def on_mouse_event(x: int, y: int, mouseButton: Button, pressed: bool) -> None:
        Log.debug(f"Mouse Event: {mouseButton.name} - {"press" if pressed else "release"}")
        try:
            if (mouseButton.name == button) and (
                (timing == "on_press" and pressed) or (timing == "on_release" and not pressed)
            ):
                if _check_modifiers(pressCtrl=pressCtrl, pressShift=pressShift, pressAlt=pressAlt, pressWin=pressWin):
                    if showNotification:
                        strAddition = _generate_addition(
                            pressCtrl=pressCtrl, pressShift=pressShift, pressAlt=pressAlt, pressWin=pressWin
                        )
                        show_notification(
                            title="LiberRPA - Mouse Trigger",
                            message=f"Mouse {timing}: [{strAddition}mouse_{button}] triggered.",
                            duration=2,
                        )

                    dictResult["result"] = func(*args)

                    listenerMouse.stop()
                    keyboard.unhook(listenerKeyboard)
                    eventStop.set()

        except Exception as e:
            Log.error(f"Error in mouse trigger: {e}")
            listenerMouse.stop()
            keyboard.unhook(listenerKeyboard)
            eventStop.set()

    listenerKeyboard = keyboard.hook(on_key_event_for_mouse)
    listenerMouse = MouseListener(on_click=on_mouse_event)
    listenerMouse.daemon = True
    listenerMouse.start()

    if block:
        # Wait for the event to be triggered
        eventStop.wait()

    return dictResult["result"]


@Log.trace()
def keyboard_trigger(
    func: Callable[..., T],
    args: list[Any] = [],
    key: HookKey = "enter",
    pressCtrl: bool = False,
    pressShift: bool = False,
    pressAlt: bool = False,
    pressWin: bool = False,
    timing: Literal["on_press", "on_release"] = "on_release",
    showNotification: bool = True,
    block: bool = True,
) -> T | None:
    """
    Trigger a specified function when the given key and modifier keys are pressed/released.

    Parameters:
        func: The function to execute when the trigger is activated.
        args: Arguments to pass to the function.
        key: Key to listen for. All supported key in the type "HookKey" (If a symbol is typed with Shift, note to set pressShift=True): ['ctrl', 'left ctrl', 'right ctrl', 'shift', 'left shift', 'right shift', 'alt', 'left alt', 'right alt', 'windows', 'left windows', 'right windows', 'tab', 'space', 'enter', 'esc', 'caps lock', 'left menu', 'right menu', 'backspace', 'insert', 'delete', 'end', 'home', 'page up', 'page down', 'left', 'up', 'right', 'down', 'print screen', 'scroll lock', 'pause', 'num lock', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', '`', '~', '!', '@', '#', '$', '%', '^', '&', '*', '(', ')', '-', '_', '=', '+', '[', '{', ']', '}', '\\\\', '|', ';', ':', "'", '"', ',', '<', '.', '>', '/', '?', 'separator', 'decimal', 'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12', 'f13', 'f14', 'f15', 'f16', 'f17', 'f18', 'f19', 'f20', 'f21', 'f22', 'f23', 'f24', 'browser back', 'browser forward', 'browser refresh', 'browser stop', 'browser search key', 'browser favorites', 'browser start and home', 'volume mute', 'volume down', 'volume up', 'next track', 'previous track', 'stop media', 'play/pause media', 'start mail', 'select media', 'start application 1', 'start application 2', 'spacebar', 'clear', 'select', 'print', 'execute', 'help', 'control-break processing', 'applications', 'sleep'] (2 backslash is not visual in Pylance, so use 4 backslash to express one visual backslash.)
        pressCtrl: Whether the Ctrl key must be pressed. Set it be True if key is 'ctrl', 'left ctrl', 'right ctrl' and timing is "on_press"
        pressShift: Whether the Shift key must be pressed. Set it be True if key is 'shift', 'left shift', 'right shift' and timing is "on_press"
        pressAlt: Whether the Alt key must be pressed. Set it be True if key is 'alt', 'left alt', 'right alt' and timing is "on_press"
        pressWin: Whether the Win key must be pressed. Set it be True if key is 'windows', 'left windows', 'right windows' and timing is "on_press"
        timing: When to trigger the function, "on_press" or "on_release".
        showNotification: Whether to show a notification when the function is triggered.
        block: Whether to block the main thread until the trigger is executed.

    Returns:
        T|None: The return value of the executed function if block=True, or None otherwise.
    """

    listKeys: list[str] = list(HookKey.__args__)
    if key not in listKeys:
        raise ValueError(f"The argument key({key}) should be one of {listKeys}")

    _check_timing(timing=timing)

    dictResult: dict[str, T | None] = {"result": None}
    eventStop = threading.Event()

    def on_key_event_for_keyboard(event: keyboard.KeyboardEvent) -> None:
        try:
            strKeyName, boolPressed = _get_keyname_and_press(event=event)
            print(boolPressed)

            if (strKeyName == key) and (
                (timing == "on_press" and boolPressed) or (timing == "on_release" and not boolPressed)
            ):
                if _check_modifiers(
                    pressCtrl=pressCtrl,
                    pressShift=pressShift,
                    pressAlt=pressAlt,
                    pressWin=pressWin,
                ):
                    if showNotification:
                        strAddition = _generate_addition(
                            pressCtrl=pressCtrl, pressShift=pressShift, pressAlt=pressAlt, pressWin=pressWin
                        )
                        show_notification(
                            title="LiberRPA - Keyboard Trigger",
                            message=f"Keyboard {timing}: [{strAddition}{key}] triggered.",
                            duration=2,
                        )

                    dictResult["result"] = func(*args)

                    keyboard.unhook(listenerKeyboard)
                    eventStop.set()

        except Exception as e:
            Log.error(f"Error in keyboard trigger: {e}")
            keyboard.unhook(listenerKeyboard)
            eventStop.set()

    listenerKeyboard = keyboard.hook(on_key_event_for_keyboard)

    if block:
        eventStop.wait()

    return dictResult["result"]


def register_force_exit() -> None:
    """LiberRPA Main block will invoke it, should not invoke it by user."""

    # Only works on the MainProcess
    if multiprocessing.current_process().name != "MainProcess":
        Log.error("Should only invoke hotkey_exit() in main process.")
        return None

    def on_hotkey_pressed() -> None:
        # Assign the value to record exit reason.
        End.executorPackageStatus = "terminated"
        End.cleanup()
        print("on_hotkey_pressed - os._exit")
        os._exit(0)

    try:
        keyboard.add_hotkey("ctrl+f12", on_hotkey_pressed)
        # Start a thread to keep the keyboard listener active
        threading.Thread(target=keyboard.wait, daemon=True).start()

    except Exception as e:
        Log.error(f"Failed to register Ctrl+F12 hotkey: {e}")


def _listen_for_exit() -> None:
    for line in sys.stdin:
        if line.strip() == "Executor-terminated":
            Log.critical("Terminated by Executor.")
            End.executorPackageStatus = "terminated"
            End.cleanup()
            print("_handle_sigterm - os._exit")
            os._exit(0)


# Start the stdin listener thread.
listener_thread = threading.Thread(target=_listen_for_exit, daemon=True)
listener_thread.start()


if __name__ == "__main__":

    def my_function_1():
        print("Triggered function executed!")
        return "Done"

    def my_function_2(text: str) -> str:
        print("Triggered function executed! " + text)
        return "Done " + text

    """ print(
        mouse_trigger(
            func=my_function_1,
            args=[],
            button="left",
            pressCtrl=True,
            pressAlt=False,
            pressShift=False,
            pressWin=False,
            timing="on_release",
            showNotification=True,
            block=True,
        )
    ) """

    """ print(
        keyboard_trigger(
            func=my_function_2,
            args=["22"],
            key="a",
            pressCtrl=True,
            pressAlt=False,
            pressShift=False,
            pressWin=False,
            timing="on_release",
            showNotification=True,
            block=True,
        )
    ) """
    """ print(
        keyboard_trigger(
            func=my_function_2,
            args=["22"],
            key="right windows",
            pressCtrl=False,
            pressAlt=False,
            pressShift=False,
            pressWin=False,
            timing="on_release",
            showNotification=True,
            block=True,
        )
    ) """

    register_force_exit()

    import time

    for idx in range(0, 5, 1):
        time.sleep(1)
        print(idx)
