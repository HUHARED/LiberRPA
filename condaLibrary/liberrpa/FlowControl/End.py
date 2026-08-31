# FileName: End.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._RunContext import write_executor_run_state
from liberrpa.Common._Utils import PROCESS_NAME
import liberrpa.UI._TerminableThread as _TerminableThread
from liberrpa.Dialog import show_notification
from liberrpa.FlowControl.ProjectFlowInit import PrjArgs

from datetime import timedelta
import sys
import threading
from typing import Literal

type FlowExecutionResult = Literal["completed", "error", "terminated"]

# The final execution result of the current Flow. Executor maps "terminated" to "cancel" or "timeout" according to the action that requested termination.
executionResult: FlowExecutionResult = "completed"

_LOCK_CLEANUP = threading.Lock()
_EVENT_CLEANUP_FINISHED = threading.Event()
_boolCleanupStarted = False
_cleanupError: BaseException | None = None


@Log.trace()
def cleanup() -> None:
    global _boolCleanupStarted, _cleanupError

    if PROCESS_NAME != "MainProcess":
        # Only run cleanup in MainProcess.
        return None

    with _LOCK_CLEANUP:
        boolWaitForCleanup = _boolCleanupStarted
        _boolCleanupStarted = True

    if boolWaitForCleanup:
        # Do not exit the process while another thread is still cleaning up.
        _EVENT_CLEANUP_FINISHED.wait()
        if _cleanupError is not None:
            raise RuntimeError("Flow cleanup failed.") from _cleanupError
        return None

    try:
        dictResultMessage = {
            "completed": f"{PrjArgs.projectName} - Completed.",
            "error": f"{PrjArgs.projectName} - Encounter an error.",
            "terminated": f"{PrjArgs.projectName} - You pressed Ctrl+F12 or Executor stopped it.",
        }

        show_notification(
            title="LiberRPA",
            message=dictResultMessage[executionResult],
            duration=2,
            wait=False,
        )

        Log.info(f"Elapsed time: {timedelta(seconds=int(PrjArgs.elapsedTime))}")

        """
        Summarize unsafe timeout fallback events at process end.
        These counters are read from the module instead of imported by value, because integers are immutable and `from module import counter` would not track later rebinding in _TerminableThread.
        """
        if (
            _TerminableThread.intUnsafeThreadTerminationCount > 0
            or _TerminableThread.intUnstoppableThreadCount > 0
        ):
            strTemp = ""

            if _TerminableThread.intUnsafeThreadTerminationCount > 0:
                # The worker thread was actually interrupted by injected exception and then stopped.
                strTemp += (
                    f"Unsafe timeout fallback interrupted worker threads "
                    f"{_TerminableThread.intUnsafeThreadTerminationCount} times. "
                )

            if _TerminableThread.intUnstoppableThreadCount > 0:
                # The worker thread could not be stopped. The specific call raised UiUnstoppableThreadError.
                strTemp += (
                    f"Unsafe timeout fallback failed to stop worker threads "
                    f"{_TerminableThread.intUnstoppableThreadCount} times. "
                )

            Log.critical(
                strTemp + "This means a UI or third-party call did not return in time. "
                "Please report this case with logs if it happens repeatedly."
            )

        # Capture late termination requests, then use one result for the state and final log.
        strExecutionResult = executionResult
        write_executor_run_state(status=strExecutionResult, logPath=Log.strLogFolder)
        Log.debug(dictResultMessage[strExecutionResult])
    except BaseException as e:
        _cleanupError = e
        raise
    finally:
        # Release every waiter even if cleanup raises or requests process exit.
        _EVENT_CLEANUP_FINISHED.set()


def main() -> None:
    cleanup()
    # Stop the current process.
    Log.info(f"'{PROCESS_NAME}' exit.")
    sys.exit()


if __name__ == "__main__":
    main()
