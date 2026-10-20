# FileName: cleanup_loop.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging
import sys
import time
from threading import Event

import django

django.setup()

from django.core.management import call_command
from django.db import DatabaseError

from console_project.workers import stop_on_signals
from operations.models import CleanupTask
from operations.cleanup import DICT_CLEANUP_INTERVAL_SECONDS

_LOGGER = logging.getLogger("console.cleanup")
_DICT_COMMAND = {
    CleanupTask.FILE_STORAGE: "cleanup_file_storage",
    CleanupTask.RUN_DATA: "cleanup_run_data",
    CleanupTask.EMAIL_HISTORY: "prune_email_deliveries",
    CleanupTask.AUDIT_HISTORY: "prune_audit_records",
    CleanupTask.API_KEYS: "prune_api_keys",
}


def main() -> None:
    boolFiles = sys.argv[1] == "files"
    listTask = [
        task for task in CleanupTask if (task == CleanupTask.FILE_STORAGE) == boolFiles
    ]
    dictNextRun = dict.fromkeys(listTask, 0.0)
    stopEvent = Event()
    with stop_on_signals(stopEvent):
        while not stopEvent.is_set():
            for task in listTask:
                if stopEvent.is_set():
                    break
                if time.monotonic() < dictNextRun[task]:
                    continue
                dictNextRun[task] = time.monotonic() + DICT_CLEANUP_INTERVAL_SECONDS[task]
                try:
                    call_command(_DICT_COMMAND[task])
                except DatabaseError:
                    raise
                except Exception as e:
                    _LOGGER.error("%s cleanup failed: %s", task.label, type(e).__name__)
            stopEvent.wait(max(0.1, min(dictNextRun.values()) - time.monotonic()))


if __name__ == "__main__":
    main()
