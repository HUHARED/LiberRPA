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


# The event to check whether mouse left or ESC is pressed.
eventMouseLeftPressed = threading.Event()
eventEscPressed = threading.Event()
eventStopRequested = threading.Event()


def should_continue_hook() -> bool:
    boolShouldContinue = not (eventMouseLeftPressed.is_set() or eventEscPressed.is_set() or eventStopRequested.is_set())
    if eventMouseLeftPressed.is_set():
        Log.critical("Pressed Mouse Left???")
    if eventEscPressed.is_set():
        Log.critical("Pressed ESC???")

    return boolShouldContinue


def check_ESC_pressed() -> bool:
    return eventEscPressed.is_set()


@Log.trace()
def _reset_event() -> None:
    eventMouseLeftPressed.clear()
    eventEscPressed.clear()
    eventStopRequested.clear()


@Log.trace()
def request_stop(source: str = "") -> None:
    Log.debug("request_stop-" + source)
    eventStopRequested.set()


def _on_mouse_left_press(event: MouseEvent) -> bool | None:
    if event.MessageName == "mouse left down":
        Log.critical("mouse left down")
        eventMouseLeftPressed.set()

        # Block the mouse left button down event
        return False
    return None


@Log.trace()
def subscribe_mouse_left() -> None:
    hm.SubscribeMouseLeftDown(_on_mouse_left_press)


def _on_esc_press(event: KeyboardEvent) -> bool | None:
    if event.KeyID == 0x1B:  # ESC key
        Log.critical("Press ESC.")
        eventEscPressed.set()

        # Block the ESC key event
        return False
    return None


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

        Log.critical("PumpMessages start.")
        # pythoncom.PumpMessages() can not be quit, I don't know why, so use while and pythoncom.PumpWaitingMessages() to capture hook.
        while should_continue_hook():
            pythoncom.PumpWaitingMessages()
            # Reduce CPU occupation.
            time.sleep(0.001)
        Log.critical("PumpMessages done.")

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
