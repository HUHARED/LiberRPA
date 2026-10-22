# FileName: End.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Logging import Log
from liberrpa.Common._RunContext import (
    ExecutorRunStateStatus,
    capture_output_snapshot,
    capture_execution_error,
    write_executor_run_state,
)
from liberrpa.Common._Utils import PROCESS_NAME
import liberrpa.UI._TerminableThread as _TerminableThread
from liberrpa.Dialog import show_notification
from liberrpa.FlowControl.ProjectFlowInit import PrjArgs, _executorEmailOutputKeys

from datetime import timedelta
import json
import sys
import threading


# The final execution result of the current Flow. Executor maps "terminated" to "canceled" or "timed_out" according to the action that requested termination.
executionResult = ExecutorRunStateStatus.COMPLETED
executionError: Exception | None = None

_LOCK_CLEANUP = threading.Lock()
_EVENT_CLEANUP_FINISHED = threading.Event()
_boolCleanupStarted = False
_cleanupError: BaseException | None = None


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
        emailOutputKeys: list[str] = []
        if executionResult == ExecutorRunStateStatus.COMPLETED:
            emailOutputKeys = _executorEmailOutputKeys["completed"]
        elif executionResult == ExecutorRunStateStatus.ERROR:
            emailOutputKeys = _executorEmailOutputKeys["error"]
        outputSnapshot, emailOutputContext = capture_output_snapshot(
            PrjArgs.customArgs, emailOutputKeys
        )
        # Capture late termination requests, then use one result for the state and diagnostics.
        finalResult = executionResult
        if finalResult == ExecutorRunStateStatus.TERMINATED:
            emailOutputContext = []
        errorSummary = (
            capture_execution_error(executionError)
            if finalResult == ExecutorRunStateStatus.ERROR
            else None
        )
        write_executor_run_state(
            status=finalResult,
            logPath=Log.strLogFolder,
            outputs=outputSnapshot,
            errorSummary=errorSummary,
            emailOutputContext=emailOutputContext,
        )

        try:
            dictResultMessage = {
                ExecutorRunStateStatus.COMPLETED: f"{PrjArgs.projectName} - Completed.",
                ExecutorRunStateStatus.ERROR: f"{PrjArgs.projectName} - An error occurred.",
                ExecutorRunStateStatus.TERMINATED: f"{PrjArgs.projectName} - Stopped.",
            }
            show_notification(
                title="LiberRPA",
                message=dictResultMessage[finalResult],
                duration=2,
                wait=False,
            )

            Log.info(f"Elapsed time: {timedelta(seconds=int(PrjArgs.elapsedTime))}")
            Log.debug(
                f"Final output snapshot: {json.dumps(outputSnapshot, ensure_ascii=False, indent=4)}"
            )

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
                    strTemp += f"Unsafe timeout fallback interrupted worker threads {_TerminableThread.intUnsafeThreadTerminationCount} times. "

                if _TerminableThread.intUnstoppableThreadCount > 0:
                    # The worker thread could not be stopped. The specific call raised UiUnstoppableThreadError.
                    strTemp += f"Unsafe timeout fallback failed to stop worker threads {_TerminableThread.intUnstoppableThreadCount} times. "

                Log.critical(
                    strTemp
                    + "This means a UI or third-party call did not return in time. "
                    "Please report this case with logs if it happens repeatedly."
                )

            Log.debug(dictResultMessage[finalResult])
            Log.info(f"'{PROCESS_NAME}' exit.")
        except Exception:
            # Notifications and diagnostics must not change the saved execution result.
            pass
    except BaseException as e:
        _cleanupError = e
        raise
    finally:
        # Release every waiter even if cleanup raises or requests process exit.
        _EVENT_CLEANUP_FINISHED.set()


def main() -> None:
    cleanup()
    sys.exit()


if __name__ == "__main__":
    main()
