# FileName: Trigger.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._Utils import PROCESS_NAME
from liberrpa.Dialog import show_notification
from liberrpa.Common._TypedValue import MouseButton, HookKey
import liberrpa.FlowControl.End as End

from pynput.mouse import Button, Listener as MouseListener
import keyboard
import threading
import time
import os
import sys
from typing import Any, Literal, overload, cast
from collections.abc import Callable


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

    return (strKeyName, boolPressed)


def _check_modifiers(
    pressCtrl: bool,
    pressShift: bool,
    pressAlt: bool,
    pressWin: bool,
) -> bool:
    return (
        keyboard.is_pressed("ctrl") == pressCtrl
        and keyboard.is_pressed("shift") == pressShift
        and keyboard.is_pressed("alt") == pressAlt
        and keyboard.is_pressed("windows") == pressWin
    )


def _check_at_least_one_modifier(
    pressCtrl: bool,
    pressShift: bool,
    pressAlt: bool,
    pressWin: bool,
) -> None:
    if not any((pressCtrl, pressShift, pressAlt, pressWin)):
        raise ValueError(
            "A trigger must require at least one modifier key. "
            "Set at least one of pressCtrl, pressShift, pressAlt, or pressWin to True."
        )


@overload
def mouse_trigger[T](
    func: Callable[..., T],
    args: list[Any] | None = None,
    button: MouseButton = "left",
    pressCtrl: bool = False,
    pressShift: bool = False,
    pressAlt: bool = False,
    pressWin: bool = False,
    timing: Literal["on_press", "on_release"] = "on_release",
    notify: bool = True,
    *,
    block: Literal[False],
) -> None: ...


@overload
def mouse_trigger[T](
    func: Callable[..., T],
    args: list[Any] | None = None,
    button: MouseButton = "left",
    pressCtrl: bool = False,
    pressShift: bool = False,
    pressAlt: bool = False,
    pressWin: bool = False,
    timing: Literal["on_press", "on_release"] = "on_release",
    notify: bool = True,
    *,
    block: Literal[True] = True,
) -> T: ...


@Log.trace()
def mouse_trigger[T](
    func: Callable[..., T],
    args: list[Any] | None = None,
    button: MouseButton = "left",
    pressCtrl: bool = False,
    pressShift: bool = False,
    pressAlt: bool = False,
    pressWin: bool = False,
    timing: Literal["on_press", "on_release"] = "on_release",
    notify: bool = True,
    *,
    block: bool = True,
) -> T | None:
    """
    Trigger a specified function when the given mouse button and modifier keys are pressed/released.

    At least one modifier key must be required. Ordinary single-key or single-click triggers are intentionally not supported, to avoid accidental execution.

    Parameters:
        func: The function to execute when the trigger is activated.
        args: Arguments to pass to the function.
        button: Mouse button, one of ["left", "right", "middle"].
        pressCtrl: Whether the Ctrl key must be pressed.
        pressShift: Whether the Shift key must be pressed.
        pressAlt: Whether the Alt key must be pressed.
        pressWin: Whether the Win key must be pressed.
        timing: When to trigger the function, "on_press" or "on_release".
        notify: Whether to show a notification when the function is triggered.
        block: Whether to block the main thread until the trigger is executed.

    Returns:
        T | None: The return value of the executed function if block=True, or None if block=False.

    Raises:
        Exception: Re-raises the exception raised by func when block=True.
    """

    args = [] if args is None else args

    listValue = ["left", "right", "middle"]
    if button not in listValue:
        raise ValueError(f"The argument button ({button}) should be one of {listValue}.")

    _check_timing(timing=timing)

    _check_at_least_one_modifier(
        pressCtrl=pressCtrl,
        pressShift=pressShift,
        pressAlt=pressAlt,
        pressWin=pressWin,
    )

    resultMissing = object()
    result: object = resultMissing
    triggerError: Exception | None = None
    eventStop = threading.Event()
    triggerLock = threading.Lock()
    triggerClaimed = False

    listenerMouse: MouseListener

    def claim_trigger() -> bool:
        nonlocal triggerClaimed

        with triggerLock:
            if triggerClaimed:
                return False
            triggerClaimed = True
            return True

    def stop_listeners() -> None:
        nonlocal triggerError

        try:
            listenerMouse.stop()
        except Exception as e:
            Log.error(f"Failed to stop mouse listener: {e}")
            if triggerError is None:
                triggerError = e

        try:
            removeKeyboardHook()
        except Exception as e:
            Log.error(f"Failed to unhook keyboard listener: {e}")
            if triggerError is None:
                triggerError = e

    def on_mouse_event(_x: int, _y: int, mouseButton: Button, pressed: bool) -> None:
        nonlocal result, triggerError

        Log.debug(
            f"Mouse Event: {mouseButton.name} - {'press' if pressed else 'release'}"
        )

        if not (
            (mouseButton.name == button)
            and (
                (timing == "on_press" and pressed)
                or (timing == "on_release" and not pressed)
            )
        ):
            return

        try:
            boolModifiersMatch = _check_modifiers(
                pressCtrl=pressCtrl,
                pressShift=pressShift,
                pressAlt=pressAlt,
                pressWin=pressWin,
            )
        except Exception as e:
            if not claim_trigger():
                return
            Log.error(f"Failed to check modifiers for mouse trigger: {e}")
            triggerError = e
            eventStop.set()
            return

        if not boolModifiersMatch or not claim_trigger():
            return

        try:
            if notify:
                strAddition = _generate_addition(
                    pressCtrl=pressCtrl,
                    pressShift=pressShift,
                    pressAlt=pressAlt,
                    pressWin=pressWin,
                )
                show_notification(
                    title="LiberRPA - Mouse Trigger",
                    message=f"Mouse {timing}: [{strAddition}mouse_{button}] triggered.",
                    duration=2,
                )

            result = func(*args)

        except Exception as e:
            Log.error(f"Error in mouse trigger: {e}")
            triggerError = e

        finally:
            eventStop.set()

    # Keep keyboard's internal pressed-key state current while waiting for a mouse event.
    # The trigger itself reads that state through is_pressed().
    removeKeyboardHook: Callable[[], None] = keyboard.hook(lambda _event: None)
    try:
        listenerMouse = MouseListener(on_click=on_mouse_event)
        listenerMouse.daemon = True
        listenerMouse.start()
    except Exception:
        removeKeyboardHook()
        raise

    if not block:

        def stop_listeners_after_trigger() -> None:
            eventStop.wait()
            stop_listeners()

        threading.Thread(target=stop_listeners_after_trigger, daemon=True).start()
        return None

    eventStop.wait()
    stop_listeners()

    if triggerError is not None:
        raise triggerError

    if result is resultMissing:
        raise RuntimeError(
            "The mouse trigger stopped before the callback returned a result."
        )

    return cast(T, result)


@overload
def keyboard_trigger[T](
    func: Callable[..., T],
    args: list[Any] | None = None,
    key: HookKey = "enter",
    pressCtrl: bool = False,
    pressShift: bool = False,
    pressAlt: bool = False,
    pressWin: bool = False,
    timing: Literal["on_press", "on_release"] = "on_release",
    notify: bool = True,
    *,
    block: Literal[False],
) -> None: ...


@overload
def keyboard_trigger[T](
    func: Callable[..., T],
    args: list[Any] | None = None,
    key: HookKey = "enter",
    pressCtrl: bool = False,
    pressShift: bool = False,
    pressAlt: bool = False,
    pressWin: bool = False,
    timing: Literal["on_press", "on_release"] = "on_release",
    notify: bool = True,
    *,
    block: Literal[True] = True,
) -> T: ...


@Log.trace()
def keyboard_trigger[T](
    func: Callable[..., T],
    args: list[Any] | None = None,
    key: HookKey = "enter",
    pressCtrl: bool = False,
    pressShift: bool = False,
    pressAlt: bool = False,
    pressWin: bool = False,
    timing: Literal["on_press", "on_release"] = "on_release",
    notify: bool = True,
    *,
    block: bool = True,
) -> T | None:
    """
    Trigger a specified function when the given key and modifier keys are pressed/released.

    At least one modifier key must be required. Ordinary single-key or single-click triggers are intentionally not supported, to avoid accidental execution.

    Parameters:
        func: The function to execute when the trigger is activated.
        args: Arguments to pass to the function.
        key: Key to listen for. All supported key in the type "HookKey" (If a symbol is typed with Shift, note to set pressShift=True): ['ctrl', 'left ctrl', 'right ctrl', 'shift', 'left shift', 'right shift', 'alt', 'left alt', 'right alt', 'windows', 'left windows', 'right windows', 'tab', 'space', 'enter', 'esc', 'caps lock', 'left menu', 'right menu', 'backspace', 'insert', 'delete', 'end', 'home', 'page up', 'page down', 'left', 'up', 'right', 'down', 'print screen', 'scroll lock', 'pause', 'num lock', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', '`', '~', '!', '@', '#', '$', '%', '^', '&', '*', '(', ')', '-', '_', '=', '+', '[', '{', ']', '}', '\\', '|', ';', ':', "'", '"', ',', '<', '.', '>', '/', '?', 'separator', 'decimal', 'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12', 'f13', 'f14', 'f15', 'f16', 'f17', 'f18', 'f19', 'f20', 'f21', 'f22', 'f23', 'f24', 'browser back', 'browser forward', 'browser refresh', 'browser stop', 'browser search key', 'browser favorites', 'browser start and home', 'volume mute', 'volume down', 'volume up', 'next track', 'previous track', 'stop media', 'play/pause media', 'start mail', 'select media', 'start application 1', 'start application 2', 'spacebar', 'clear', 'select', 'print', 'execute', 'help', 'control-break processing', 'applications', 'sleep']
        pressCtrl: Whether the Ctrl key must be pressed. Set it be True if key is 'ctrl', 'left ctrl', 'right ctrl' and timing is "on_press"
        pressShift: Whether the Shift key must be pressed. Set it be True if key is 'shift', 'left shift', 'right shift' and timing is "on_press"
        pressAlt: Whether the Alt key must be pressed. Set it be True if key is 'alt', 'left alt', 'right alt' and timing is "on_press"
        pressWin: Whether the Win key must be pressed. Set it be True if key is 'windows', 'left windows', 'right windows' and timing is "on_press"
        timing: When to trigger the function, "on_press" or "on_release".
        notify: Whether to show a notification when the function is triggered.
        block: Whether to block the main thread until the trigger is executed.

    Returns:
        T | None: The return value of the executed function if block=True, or None if block=False.

    Raises:
        Exception: Re-raises the exception raised by func when block=True.
    """

    args = [] if args is None else args

    listKeys: list[str] = list(HookKey.__args__)
    if key not in listKeys:
        raise ValueError(f"The argument key ({key}) should be one of {listKeys}.")

    _check_timing(timing=timing)

    _check_at_least_one_modifier(
        pressCtrl=pressCtrl,
        pressShift=pressShift,
        pressAlt=pressAlt,
        pressWin=pressWin,
    )

    resultMissing = object()
    result: object = resultMissing
    triggerError: Exception | None = None
    eventStop = threading.Event()
    triggerLock = threading.Lock()
    triggerClaimed = False

    def claim_trigger() -> bool:
        nonlocal triggerClaimed

        with triggerLock:
            if triggerClaimed:
                return False
            triggerClaimed = True
            return True

    def unhook_keyboard() -> None:
        nonlocal triggerError

        try:
            removeKeyboardHook()
        except Exception as e:
            Log.error(f"Failed to unhook keyboard listener: {e}")
            if triggerError is None:
                triggerError = e

    def on_key_event_for_keyboard(event: keyboard.KeyboardEvent) -> None:
        nonlocal result, triggerError

        try:
            strKeyName, boolPressed = _get_keyname_and_press(event=event)
        except ValueError as e:
            Log.warning(f"Ignored keyboard event: {e}")
            return

        if not (
            (strKeyName == key)
            and (
                (timing == "on_press" and boolPressed)
                or (timing == "on_release" and not boolPressed)
            )
        ):
            return

        try:
            modifiersMatch = _check_modifiers(
                pressCtrl=pressCtrl,
                pressShift=pressShift,
                pressAlt=pressAlt,
                pressWin=pressWin,
            )
        except Exception as e:
            if not claim_trigger():
                return
            Log.error(f"Failed to check modifiers for keyboard trigger: {e}")
            triggerError = e
            eventStop.set()
            return

        if not modifiersMatch or not claim_trigger():
            return

        try:
            if notify:
                strAddition = _generate_addition(
                    pressCtrl=pressCtrl,
                    pressShift=pressShift,
                    pressAlt=pressAlt,
                    pressWin=pressWin,
                )
                show_notification(
                    title="LiberRPA - Keyboard Trigger",
                    message=f"Keyboard {timing}: [{strAddition}{key}] triggered.",
                    duration=2,
                )

            result = func(*args)

        except Exception as e:
            Log.error(f"Error in keyboard trigger: {e}")
            triggerError = e

        finally:
            eventStop.set()

    removeKeyboardHook: Callable[[], None] = keyboard.hook(on_key_event_for_keyboard)

    if not block:

        def unhook_keyboard_after_trigger() -> None:
            eventStop.wait()
            unhook_keyboard()

        threading.Thread(target=unhook_keyboard_after_trigger, daemon=True).start()
        return None

    eventStop.wait()
    unhook_keyboard()

    if triggerError is not None:
        raise triggerError

    if result is resultMissing:
        raise RuntimeError(
            "The keyboard trigger stopped before the callback returned a result."
        )

    return cast(T, result)


def _register_force_exit() -> None:
    """LiberRPA Main block will invoke it, should not invoke it by user."""

    # Only works on the MainProcess
    if PROCESS_NAME != "MainProcess":
        Log.error("Should only invoke hotkey_exit() in main process.")
        return None

    def on_hotkey_pressed() -> None:
        # Assign the value to record exit reason.
        End.executionResult = "terminated"
        End.cleanup()
        Log.verbose("on_hotkey_pressed - os._exit")
        os._exit(0)

    try:
        keyboard.add_hotkey("ctrl+f12", on_hotkey_pressed)

    except Exception as e:
        Log.error(f"Failed to register Ctrl+F12 hotkey: {e}")


_FLOAT_EXECUTOR_EXIT_POLL_SECONDS = 0.05
_INT_EXECUTOR_EXIT_READ_BYTES = 4096


def _listen_for_exit(stdinFd: int) -> None:
    # Use only raw, non-blocking reads on Executor's private command pipe.
    # A pending blocking stdin read can hang a new Windows Python interpreter:
    # https://github.com/python/cpython/issues/78961
    bytesPending = b""
    while True:
        try:
            bytesChunk = os.read(stdinFd, _INT_EXECUTOR_EXIT_READ_BYTES)
        except BlockingIOError:
            time.sleep(_FLOAT_EXECUTOR_EXIT_POLL_SECONDS)
            continue
        except OSError as e:
            Log.error(f"Failed to read the Executor termination pipe: {e}")
            return

        # A pipe read need not contain a complete line. Accept CRLF, LF, or CR.
        bytesPending += bytesChunk.replace(b"\r", b"\n")
        listLine = bytesPending.split(b"\n")
        bytesPending = listLine.pop()
        if not bytesChunk:
            # Preserve the previous text-stream behavior for a final unterminated line.
            listLine.append(bytesPending)
            bytesPending = b""

        for bytesLine in listLine:
            if bytesLine.strip() == b"Executor-terminated":
                Log.critical("Terminated by Executor.")
                End.executionResult = "terminated"
                End.cleanup()
                Log.verbose("_handle_sigterm - os._exit")
                os._exit(0)
                return

        if not bytesChunk:
            return
        if len(bytesPending) > _INT_EXECUTOR_EXIT_READ_BYTES:
            Log.error(
                "Executor termination pipe received an oversized unterminated command."
            )
            return


# Start the stdin listener thread.
_listenerThread: threading.Thread | None = None
_listenerThreadLock = threading.Lock()


def _register_executor_exit_listener() -> None:
    """Start the Executor stdin listener once in the current process."""

    global _listenerThread

    with _listenerThreadLock:
        if _listenerThread is not None:
            return

        intStdinFd = sys.stdin.fileno()
        # Python 3.12+ supports non-blocking Windows pipes.
        # Configure this before starting the reader, and fail visibly instead of falling back to a blocking read.
        os.set_blocking(intStdinFd, False)
        threadListener = threading.Thread(
            target=_listen_for_exit,
            args=(intStdinFd,),
            name="LiberRPAExecutorExitListener",
            daemon=True,
        )
        threadListener.start()
        _listenerThread = threadListener
        Log.debug("Executor stdin listener started in non-blocking mode.")


if __name__ == "__main__":

    def my_function_1() -> Literal["Done"]:
        print("Triggered function executed!")
        return "Done"

    def my_function_2(text: str) -> str:
        print("Triggered function executed! " + text)
        return "Done " + text

    print(
        mouse_trigger(
            func=my_function_1,
            args=[],
            button="left",
            pressCtrl=True,
            pressAlt=False,
            pressShift=False,
            pressWin=False,
            timing="on_release",
            notify=True,
            block=True,
        )
    )

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
            notify=True,
            block=False,
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
            notify=True,
            block=True,
        )
    ) """

    _register_force_exit()

    import time

    for idx in range(0, 5, 1):
        time.sleep(1)
        print(idx)
