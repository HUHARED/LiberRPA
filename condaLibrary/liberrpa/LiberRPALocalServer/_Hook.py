# FileName: _Hook.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from pyWinhook import HookManager, MouseEvent, KeyboardEvent
import pythoncom
import sys
import signal
import atexit
import threading
import time
from types import FrameType


# The job must to do before exiting.
def normal_exit() -> None:
    Log.verbose("normal_exit, sys.exit(0)")
    sys.exit(0)


# Create hook manager.
try:
    hm = HookManager()
except Exception as e:
    Log.exception_info(e)
    raise SystemExit(1) from e


# The events used by the indication loop and the hook thread.
eventMouseLeftPressed = threading.Event()
eventMouseLeftReleased = threading.Event()
eventEscPressed = threading.Event()
eventStopRequested = threading.Event()

_lockMouseLeftPosition = threading.Lock()
_tupleMouseLeftPosition: tuple[int, int] | None = None


def should_continue_hook() -> bool:
    return not (
        eventMouseLeftPressed.is_set()
        or eventEscPressed.is_set()
        or eventStopRequested.is_set()
    )


def check_ESC_pressed() -> bool:
    return eventEscPressed.is_set()


def get_mouse_left_position() -> tuple[int, int] | None:
    with _lockMouseLeftPosition:
        return _tupleMouseLeftPosition


def wait_mouse_left_released(timeout: float) -> bool:
    return eventMouseLeftReleased.wait(timeout=timeout)


def _should_keep_hooking() -> bool:
    # A selection event stops the indication loop, but the hook must remain active until post-selection processing finishes so the complete click is suppressed.
    return not eventStopRequested.is_set()


@Log.trace()
def _reset_event() -> None:
    global _tupleMouseLeftPosition

    eventMouseLeftPressed.clear()
    eventMouseLeftReleased.clear()
    eventEscPressed.clear()
    eventStopRequested.clear()

    with _lockMouseLeftPosition:
        _tupleMouseLeftPosition = None


@Log.trace()
def request_stop(source: str = "") -> None:
    Log.debug("request_stop-" + source)
    eventStopRequested.set()


def _on_mouse_left_press(event: MouseEvent) -> bool:
    global _tupleMouseLeftPosition

    # Keep the first mouse-down position for the current indication.
    # Additional clicks remain blocked until the caller finishes processing the selection.
    if not eventMouseLeftPressed.is_set():
        Log.debug("Mouse left down.")
        with _lockMouseLeftPosition:
            _tupleMouseLeftPosition = event.Position

        eventMouseLeftReleased.clear()
        eventMouseLeftPressed.set()

    # Block the mouse button down event.
    return False


def _on_mouse_left_release(_event: MouseEvent) -> bool:
    if not eventMouseLeftPressed.is_set():
        return True

    Log.debug("Mouse left up.")
    eventMouseLeftReleased.set()

    # Block the matching mouse button up event as well.
    return False


@Log.trace()
def subscribe_mouse_left() -> None:
    hm.SubscribeMouseLeftDown(_on_mouse_left_press)
    hm.SubscribeMouseLeftUp(_on_mouse_left_release)


def _on_esc_press(event: KeyboardEvent) -> bool:
    if event.KeyID == 0x1B:  # ESC key
        Log.debug("Press ESC.")
        eventEscPressed.set()

        # Block the ESC key event.
        return False

    return True


@Log.trace()
def subscribe_esc() -> None:
    hm.SubscribeKeyDown(_on_esc_press)


@Log.trace()
def _unhook(source: str = "") -> None:
    Log.debug("unhook-" + source)
    hm.UnhookMouse()
    hm.UnhookKeyboard()


@Log.trace()
def hook_in_another_thread() -> None:
    _reset_event()

    try:
        Log.debug("Hook mouse and keyboard.")
        hm.HookMouse()
        hm.HookKeyboard()

        Log.debug("PumpMessages start.")
        # Keep the hook alive until the caller explicitly requests cleanup.
        while _should_keep_hooking():
            pythoncom.PumpWaitingMessages()
            # Reduce CPU occupation.
            time.sleep(0.001)
        Log.debug("PumpMessages done.")

    finally:
        _unhook(source="hook_in_another_thread")


# The quit command from cmd.
def signal_handler(sig: int, _frame: FrameType | None) -> None:
    Log.critical("Signal received:", sig)
    _unhook(source="signal_handler")
    normal_exit()


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Ensure unhook is called on program exit
atexit.register(request_stop)


if __name__ == "__main__":
    import time

    hm.HookMouse()
    hm.HookKeyboard()
    timeStart = time.monotonic()
    while True:
        if time.monotonic() - timeStart <= 10:
            pythoncom.PumpWaitingMessages()
        else:
            break
