# FileName: workers.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import signal
from collections.abc import Generator
from contextlib import contextmanager
from threading import Event
from types import FrameType


@contextmanager
def stop_on_signals(stopEvent: Event) -> Generator[None]:
    """Finish the current work item before stopping and wake an idle worker immediately."""

    def request_stop(_signalNumber: int, _frame: FrameType | None) -> None:
        stopEvent.set()

    tupleSignal = (signal.SIGINT, signal.SIGTERM)
    dictPreviousSignalHandler = {
        signalNumber: signal.getsignal(signalNumber) for signalNumber in tupleSignal
    }
    try:
        for signalNumber in tupleSignal:
            signal.signal(signalNumber, request_stop)
        yield
    finally:
        for signalNumber, previousHandler in dictPreviousSignalHandler.items():
            if previousHandler is not None:
                signal.signal(signalNumber, previousHandler)
