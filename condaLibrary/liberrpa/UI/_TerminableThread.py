# FileName: _TerminableThread.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Common._Exception import (
    UiTimeoutError,
    UiUnsafeThreadTerminationError,
    UiUnstoppableThreadError,
    UiElementNotFoundError,
    ChromeElementNotFoundError,
)

import threading
import ctypes
from time import sleep, monotonic
import sys
import traceback
from typing import Any, cast
from collections.abc import Callable
from functools import wraps

"""
There are two timeout concepts in this module:

1. soft timeout
    The timeout passed by the caller. The wrapped function should normally respect this
    timeout through its own retry/deadline logic.

2. unsafe hard timeout
    soft timeout + _UNSAFE_TERMINATION_GRACE. Only when the worker thread is still alive
    after this extra grace period do we inject UiUnsafeThreadTerminationError into it.

This unsafe fallback is not a normal safe timeout mechanism. It exists only as a
last-resort diagnostic fallback for UI/third-party calls that fail to return.
"""
_UNSAFE_TERMINATION_GRACE = 10000
# User-facing desktop notifications are throttled, otherwise repeated unsafe timeouts could spam the user. Critical logs are still written every time.
_UNSAFE_TIMEOUT_NOTIFICATION_INTERVAL = 60
_lastUnsafeTimeoutNotificationTime = 0.0

# Count cases where an exception was actually injected and the worker thread then stopped.
intUnsafeThreadTerminationCount = 0

# Count cases where exception injection failed or the worker thread was still alive after injection.
intUnstoppableThreadCount = 0


def _get_thread_stack(thread: threading.Thread) -> str:
    """Return the current stack of a worker thread before unsafe termination is attempted."""
    if thread.ident is None:
        return "Thread ident is None."

    frame = sys._current_frames().get(thread.ident)
    if frame is None:
        return f"Failed to get stack for thread ident={thread.ident}."

    return "".join(traceback.format_stack(frame))


def _truncate_text(text: str, limit: int = 4000) -> str:
    """Keep critical log messages readable when the captured stack is very long."""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... <truncated>"


def _emergency_release_input() -> None:
    """
    Best-effort cleanup after an unsafe timeout.

    If a UI operation is interrupted while pressing modifier keys or mouse buttons, the physical
    input state may be left pressed. This cleanup should stay best-effort: it must never hide the
    original unsafe timeout problem.
    """
    from liberrpa.Logging import Log

    try:
        import pyautogui

        for key in ("ctrl", "shift", "alt", "win"):
            try:
                pyautogui.keyUp(key)
            except Exception as e:
                Log.error(f"Failed to release key {key!r}: {e}")

        for button in ("left", "middle", "right"):
            try:
                pyautogui.mouseUp(button=button)
            except Exception as e:
                Log.error(f"Failed to release mouse button {button!r}: {e}")

    except Exception as e:
        Log.error(f"Failed to run emergency input release: {e}")


def _notify_unsafe_timeout(functionName: str, softTimeout: int, hardTimeout: int) -> None:
    """
    Show a throttled user-facing notification for unsafe timeout fallback.

    This is intentionally throttled. A broken UI/runtime state may trigger several unsafe timeouts
    in a short time; logs should capture every event, but desktop notifications should not spam.
    """
    from liberrpa.Logging import Log

    global _lastUnsafeTimeoutNotificationTime

    timeNow = monotonic()
    # Avoid notifying frequently.
    if timeNow - _lastUnsafeTimeoutNotificationTime < _UNSAFE_TIMEOUT_NOTIFICATION_INTERVAL:
        return None

    _lastUnsafeTimeoutNotificationTime = timeNow

    try:
        from liberrpa.Dialog import show_notification

        show_notification(
            title="Critical UI Timeout",
            message=(
                f"Unsafe timeout fallback was triggered while running {functionName}.\n"
                f"Soft timeout: {softTimeout} ms.\n"
                f"Unsafe hard timeout: {hardTimeout} ms.\n"
                "Please keep the log file and report this case if possible."
            ),
            duration=10,
            wait=False,
        )
    except Exception as e:
        Log.error(f"Failed to show unsafe timeout notification: {e}")


class TerminableThread[T](threading.Thread):
    """
    Worker thread used by timeout_kill_thread().

    The normal path is simple: run the target, store either result or exception, and let the caller
    inspect them after join(). The unsafe path calls terminate(), which injects
    UiUnsafeThreadTerminationError into this thread. That is not a safe normal control-flow tool;
    it is only the last fallback when the target fails to return after the unsafe hard timeout.
    """

    def __init__(
        self,
        target: Callable[..., T],
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
    ) -> None:
        super().__init__()
        self.target = target
        self.args = args
        self.kwargs = kwargs if kwargs is not None else {}
        self.result: T | None = None
        self.exception: BaseException | None = None

    def run(self) -> None:
        try:
            self.result = self.target(*self.args, **self.kwargs)

        except BaseException as e:
            self.exception = e

    def terminate(self) -> bool:
        """
        Inject UiUnsafeThreadTerminationError into the worker thread.

        Returns:
            bool: True if an exception was injected into a still-alive thread. False means the thread had already ended or Python could not find a matching thread state.
        """

        if not self.is_alive() or self.ident is None:
            return False

        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_ulong(self.ident),
            ctypes.py_object(UiUnsafeThreadTerminationError),
        )
        if res == 0:
            # No thread state was modified. The thread may have already ended.
            return False

        if res > 1:
            # More than one thread state was modified. This should not happen. Roll back immediately by injecting None.
            ctypes.pythonapi.PyThreadState_SetAsyncExc(
                ctypes.c_ulong(self.ident),
                None,
            )
            raise SystemError("PyThreadState_SetAsyncExc affected multiple thread states and was rolled back.")

        # res == 1: exactly one thread state was modified, which means the exception was injected.
        return True


def timeout_kill_thread[T, **P](timeout: int) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Execute a function in a worker thread with retry and unsafe hard-timeout fallback.

    Normal expected behavior:
    - The wrapped function returns successfully within the soft timeout.
    - Or the wrapped function raises a normal exception.
    - Or not-found exceptions are retried until the soft timeout expires.

    Last-resort behavior:
    - If the worker thread is still alive after soft timeout + _UNSAFE_TERMINATION_GRACE, capture its stack, release input state best-effort, notify/log, and inject UiUnsafeThreadTerminationError.
    - If the thread stops after injection, raise UiUnsafeThreadTerminationError to the caller; the operation did not finish normally and should not be treated as success.
    - If the thread still does not stop, raise UiUnstoppableThreadError.
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:

        @wraps(func)
        def wrapped_func(*args: P.args, **kwargs: P.kwargs) -> T:
            from liberrpa.Logging import Log

            global intUnsafeThreadTerminationCount, intUnstoppableThreadCount

            softTimeout = timeout
            hardTimeout = softTimeout + _UNSAFE_TERMINATION_GRACE

            timeStart = monotonic()
            softDeadline = timeStart + softTimeout / 1000
            hardDeadline = timeStart + hardTimeout / 1000

            while True:
                timeRemainingHard = hardDeadline - monotonic()
                if timeRemainingHard <= 0:
                    # This should be rare. It means retry bookkeeping consumed the hard deadline before a new worker could even be started. No thread is being killed here.

                    raise UiTimeoutError(
                        f"Function {func.__name__} exceeded unsafe hard timeout before a worker thread could be started. "
                        f"softTimeout={softTimeout} ms, hardTimeout={hardTimeout} ms."
                    )

                thread = TerminableThread(
                    target=func,
                    args=args,
                    kwargs=kwargs,
                )
                thread.start()

                # Wait up to the unsafe hard deadline, not just the soft timeout. The soft timeout is expected to be handled by the wrapped function's own logic whenever possible.
                thread.join(timeRemainingHard)

                if thread.is_alive():
                    # The wrapped function did not return even after the grace period. This is the dangerous fallback path. Capture its stack before injecting anything.
                    stackText = _get_thread_stack(thread=thread)
                    stackTextShort = _truncate_text(stackText)

                    Log.critical(
                        "Unsafe UI timeout fallback triggered.\n"
                        f"Function: {func.__module__}.{func.__name__}\n"
                        f"Soft timeout: {softTimeout} ms\n"
                        f"Unsafe hard timeout: {hardTimeout} ms\n"
                        f"Thread ident: {thread.ident}\n"
                        f"Thread stack before termination:\n{stackTextShort}"
                    )

                    _emergency_release_input()

                    try:
                        boolInjected = thread.terminate()
                    except Exception as e:
                        Log.critical(f"Failed to inject timeout exception into worker thread: {e}")
                        intUnstoppableThreadCount += 1
                        _notify_unsafe_timeout(
                            functionName=f"{func.__module__}.{func.__name__}",
                            softTimeout=softTimeout,
                            hardTimeout=hardTimeout,
                        )

                        raise UiUnstoppableThreadError(
                            f"Failed to inject timeout exception into worker thread for function {func.__name__}. "
                            "Please report this case with logs if it happens repeatedly."
                        ) from e

                    # Give the injected exception a short chance to take effect.
                    thread.join(1)

                    _notify_unsafe_timeout(
                        functionName=f"{func.__module__}.{func.__name__}",
                        softTimeout=softTimeout,
                        hardTimeout=hardTimeout,
                    )

                    if thread.is_alive():
                        # The most dangerous case: the old thread may continue doing UI work while following RPA logic continues.

                        intUnstoppableThreadCount += 1
                        Log.critical("Worker thread is still alive after unsafe timeout fallback.")

                        raise UiUnstoppableThreadError(
                            f"Function {func.__name__} exceeded unsafe hard timeout. "
                            f"softTimeout={softTimeout} ms, "
                            f"hardTimeout={hardTimeout} ms. "
                            "Unsafe timeout fallback was triggered, but the worker thread did not stop. "
                            "Please report this case with logs if it happens repeatedly."
                        )

                    if boolInjected:
                        # The exception injection worked and the thread stopped. This is still not a normal completion. The target function was interrupted in the middle, so the caller must receive a specific exception instead of a successful result.
                        intUnsafeThreadTerminationCount += 1
                        Log.critical(
                            f"Function {func.__module__}.{func.__name__} was interrupted by unsafe timeout fallback. "
                            f"softTimeout={softTimeout} ms, "
                            f"hardTimeout={hardTimeout} ms. "
                            "The worker thread stopped after exception injection. "
                        )

                        raise UiUnsafeThreadTerminationError(
                            f"Function {func.__name__} was interrupted by unsafe timeout fallback. "
                            f"softTimeout={softTimeout} ms, "
                            f"hardTimeout={hardTimeout} ms. "
                            "The operation did not finish normally. "
                            "Please report this case with logs if it happens repeatedly."
                        )

                    # Race condition: the thread was alive when checked, but finished before exception injection was applied. This is not counted as unsafe termination. Fall through and handle its result/exception normally below.
                    Log.warning(
                        f"Function {func.__module__}.{func.__name__} exceeded unsafe hard timeout, "
                        "but finished before exception injection was applied. "
                        f"softTimeout={softTimeout} ms, "
                        f"hardTimeout={hardTimeout} ms."
                    )

                if thread.exception is not None:
                    # Not-found errors are normal retry signals for UI search. They do not mean the thread is unsafe; keep retrying until the soft timeout expires.
                    if isinstance(thread.exception, (UiElementNotFoundError, ChromeElementNotFoundError)):
                        timeRemainingSoft = int((softDeadline - monotonic()) * 1000)

                        if timeRemainingSoft <= 0:
                            raise UiTimeoutError(
                                f"Function {func.__name__[1:]} timed out after {softTimeout} milliseconds. "
                                f"{thread.exception}"
                            ) from thread.exception

                        sleep(min(1, timeRemainingSoft / 1000))
                        # Retry the function
                        continue

                    raise thread.exception

                # The function returned normally. If it exceeded the soft timeout but still finished before the unsafe hard timeout, returning the result is usually safer than raising a timeout, because a UI operation may already have been performed.
                timeElapsed = int((monotonic() - timeStart) * 1000)
                if timeElapsed > softTimeout:
                    Log.warning(
                        f"Function {func.__module__}.{func.__name__} returned after soft timeout "
                        f"but before unsafe hard timeout. softTimeout={softTimeout} ms, elapsed={timeElapsed} ms."
                    )

                return cast(T, thread.result)

        return wrapped_func

    return decorator
