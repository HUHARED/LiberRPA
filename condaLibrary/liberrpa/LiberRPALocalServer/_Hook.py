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


# HookManager and the indication events are process-wide resources.
# If a hook thread cannot stop or fails while installing/uninstalling hooks, reject later indications instead of resetting shared events underneath that thread.
_lockHookLifecycle = threading.Lock()
_threadHookActive: threading.Thread | None = None
_strHookUnsafeReason: str | None = None


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


def _mark_hook_unsafe(strReason: str) -> None:
    global _strHookUnsafeReason

    with _lockHookLifecycle:
        if _strHookUnsafeReason is None:
            _strHookUnsafeReason = strReason
        strReasonCurrent = _strHookUnsafeReason

    Log.critical(
        "UI Analyzer hook subsystem entered an unsafe state. "
        f"Restart LiberRPA Local Server before starting another indication. Reason: {strReasonCurrent}"
    )


def _get_hook_unsafe_error_message(strReason: str) -> str:
    return (
        "UI Analyzer hook subsystem is in an unsafe state. "
        "Restart LiberRPA Local Server before starting another indication. "
        f"Reason: {strReason}"
    )


@Log.trace()
def hook_in_another_thread() -> None:
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
    except Exception as e:
        _mark_hook_unsafe(f"Hook thread failed: {type(e).__name__}: {e}")
        Log.exception_info(e)
    finally:
        try:
            _unhook(source="hook_in_another_thread")
        except Exception as e:
            _mark_hook_unsafe(f"Failed to uninstall hooks: {type(e).__name__}: {e}")
            Log.exception_info(e)


def start_hook() -> threading.Thread:
    """Start the process-wide UI Analyzer hook thread."""
    global _threadHookActive

    with _lockHookLifecycle:
        if _strHookUnsafeReason is not None:
            raise RuntimeError(_get_hook_unsafe_error_message(_strHookUnsafeReason))

        if _threadHookActive is not None:
            if _threadHookActive.is_alive():
                raise RuntimeError("A UI Analyzer hook thread is already running.")
            _threadHookActive = None

        _reset_event()
        subscribe_mouse_left()
        subscribe_esc()

        threadHook = threading.Thread(
            target=hook_in_another_thread,
            name="UiAnalyzerHook",
            daemon=True,
        )
        _threadHookActive = threadHook
        try:
            threadHook.start()
        except Exception:
            _threadHookActive = None
            raise

    # Give the hook thread a brief opportunity to install hooks and report an immediate failure.
    time.sleep(0.01)
    if not threadHook.is_alive():
        with _lockHookLifecycle:
            strUnsafeReason = _strHookUnsafeReason

        if strUnsafeReason is None:
            strUnsafeReason = "The hook thread ended immediately after it started."
            _mark_hook_unsafe(strUnsafeReason)

        raise RuntimeError(_get_hook_unsafe_error_message(strUnsafeReason))

    return threadHook


def stop_hook(
    threadHook: threading.Thread | None,
    *,
    source: str,
    timeoutSeconds: float = 2,
    raiseOnUnsafe: bool = True,
) -> bool:
    """Stop one hook thread and return whether the hook subsystem remains safe."""
    global _threadHookActive

    if threadHook is not None and threadHook.is_alive():
        request_stop(source=source)
        threadHook.join(timeout=timeoutSeconds)

    if threadHook is not None and threadHook.is_alive():
        _mark_hook_unsafe(
            f"Hook thread {threadHook.name!r} did not stop within {timeoutSeconds} seconds."
        )

    with _lockHookLifecycle:
        if (
            threadHook is not None
            and _threadHookActive is threadHook
            and not threadHook.is_alive()
        ):
            _threadHookActive = None
        strUnsafeReason = _strHookUnsafeReason

    if strUnsafeReason is not None and raiseOnUnsafe:
        raise RuntimeError(_get_hook_unsafe_error_message(strUnsafeReason))

    return strUnsafeReason is None and (threadHook is None or not threadHook.is_alive())


def stop_active_hook(
    *,
    source: str,
    timeoutSeconds: float = 2,
    raiseOnUnsafe: bool = True,
) -> bool:
    """Stop the current hook thread, if any."""
    with _lockHookLifecycle:
        threadHook = _threadHookActive
        strUnsafeReason = _strHookUnsafeReason

    if threadHook is None:
        if strUnsafeReason is not None and raiseOnUnsafe:
            raise RuntimeError(_get_hook_unsafe_error_message(strUnsafeReason))
        return strUnsafeReason is None

    return stop_hook(
        threadHook,
        source=source,
        timeoutSeconds=timeoutSeconds,
        raiseOnUnsafe=raiseOnUnsafe,
    )


# The quit command from cmd.
def signal_handler(sig: int, _frame: FrameType | None) -> None:
    Log.critical("Signal received:", sig)
    stop_active_hook(
        source="signal_handler",
        timeoutSeconds=2,
        raiseOnUnsafe=False,
    )
    normal_exit()


def _stop_hook_at_exit() -> None:
    try:
        stop_active_hook(
            source="atexit",
            timeoutSeconds=2,
            raiseOnUnsafe=False,
        )
    except Exception as e:
        Log.exception_info(e)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
atexit.register(_stop_hook_at_exit)


if __name__ == "__main__":
    threadHook = start_hook()
    time.sleep(10)
    stop_hook(threadHook, source="__main__")
