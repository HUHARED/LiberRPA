# FileName: _OperationLock.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Common._Exception import UiUnstoppableThreadError

from collections.abc import Callable, Generator
from contextlib import contextmanager
from functools import wraps
import threading

"""
This lock should be applied to public UI APIs only.
It prevents multiple threads from manipulating the UI at the same time.
It is not bound with timeout_kill_thread().
Do not apply it to private worker functions executed by timeout_kill_thread(),
because the public API holds the lock while the worker thread is running.

This lock is for public UI-facing APIs in the current Python process.
It serializes mouse, keyboard, UIA, screenshot, image matching, and foreground-window operations.
Some read-only APIs are also locked because their results depend on a stable screen, cursor, or foreground-window state.

Do not apply this lock to private worker functions executed by timeout_kill_thread().
Public APIs hold this lock while their worker threads are running; locking worker functions would deadlock because RLock is only reentrant within the same thread.
"""
_UI_OPERATION_LOCK = threading.RLock()
_boolUiOperationUnsafe = False
_strUiOperationUnsafeReason: str | None = None


def mark_ui_operation_unsafe(reason: str) -> None:
    """
    Mark the current process as unsafe for further UI operations.

    This is used when a UI worker thread cannot be stopped safely. Continuing to send UI operations
    after that point may cause overlapping mouse, keyboard, UIA, or Chrome active-tab actions.
    """

    global _boolUiOperationUnsafe, _strUiOperationUnsafeReason

    _boolUiOperationUnsafe = True
    _strUiOperationUnsafeReason = reason


def _raise_if_ui_operation_unsafe() -> None:
    if not _boolUiOperationUnsafe:
        return None

    raise UiUnstoppableThreadError(
        "LiberRPA UI operations are disabled because a previous UI worker thread could not be stopped safely. "
        f"Reason: {_strUiOperationUnsafeReason}"
    )


@contextmanager
def ui_operation_context() -> Generator[None]:
    """Serialize UI operations in the current Python process."""

    # Fail quickly, to avoid waiting for the lock even though it is unsafe.
    _raise_if_ui_operation_unsafe()

    with _UI_OPERATION_LOCK:
        _raise_if_ui_operation_unsafe()
        yield


def lock_ui_operation[T, **P](func: Callable[P, T]) -> Callable[P, T]:
    """Decorator that serializes a public UI operation in the current Python process."""

    @wraps(func)
    def wrapped_func(*args: P.args, **kwargs: P.kwargs) -> T:
        with ui_operation_context():
            return func(*args, **kwargs)

    return wrapped_func
