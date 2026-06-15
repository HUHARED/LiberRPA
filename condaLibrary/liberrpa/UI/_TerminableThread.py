# FileName: _TerminableThread.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Common._Exception import UiTimeoutError, UiElementNotFoundError, ChromeError

import threading
import ctypes
from time import sleep, monotonic
from typing import Callable, Generic, TypeVar, ParamSpec, Any, cast

T = TypeVar("T")
P = ParamSpec("P")


class TerminableThread(threading.Thread, Generic[T]):
    """The class for killing thread when the target function is timeout."""

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
        self.exception: Exception | None = None

    def run(self) -> None:
        try:

            self.result = self.target(*self.args, **self.kwargs)

        except Exception as e:
            self.exception = e

    def terminate(self) -> None:
        if self.is_alive() and self.ident is not None:
            # print("Thread terminated.")
            res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
                ctypes.c_long(self.ident), ctypes.py_object(UiTimeoutError)
            )
            if res > 1:
                ctypes.pythonapi.PyThreadState_SetAsyncExc(self.ident, None)
                raise SystemError("PyThreadState_SetAsyncExc failed")


def timeout_kill_thread(timeout: int) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """The decorator for executing a function with retry logic and timeout control."""

    def decorator(func: Callable[P, T]) -> Callable[P, T]:

        def wrapped_func(*args: P.args, **kwargs: P.kwargs) -> T:
            timeStart = monotonic()
            timeRemaining = timeout

            while timeRemaining > 0:
                thread = TerminableThread(
                    target=func,
                    args=args,
                    kwargs=kwargs,
                )
                thread.start()
                thread.join(timeRemaining / 1000)  # Convert ms to seconds

                if thread.is_alive():
                    thread.terminate()

                    # Add more related information.
                    if thread.exception:
                        strAddition = str(thread.exception)
                    elif len(args) > 0 and isinstance(args[0], dict) and args[0].get("window"):
                        strAddition = f"Not found an uia element by the selector: {args[0]}"
                    else:
                        strAddition = ""

                    raise UiTimeoutError(
                        f"Function {func.__name__[1:]} timed out after {timeout} milliseconds. {strAddition}"
                    )

                if thread.exception:
                    if (
                        isinstance(thread.exception, UiElementNotFoundError)
                        or (isinstance(thread.exception, ChromeError))
                        and str(thread.exception).startswith("Not found the target element")
                    ):
                        # Delay 1s.
                        sleep(1)
                        # Calculate remaining time
                        timeElapsed = int((monotonic() - timeStart) * 1000)
                        timeRemaining = timeout - timeElapsed

                        if timeRemaining <= 0:
                            raise UiTimeoutError(
                                f"Function {func.__name__[1:]} timed out after {timeout} milliseconds. {thread.exception}"
                            )
                        # Retry the function
                        continue

                    raise thread.exception

                # If the function executed successfully, return the result
                return cast(T, thread.result)

            # If we exit the loop without success, raise UiTimeoutError
            raise UiTimeoutError(
                f"(!!!It should not appear.) Function {func.__name__[1:]} timed out after {timeout} milliseconds."
            )

        return wrapped_func

    return decorator
