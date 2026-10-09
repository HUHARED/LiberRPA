# FileName: run_job_worker.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from threading import Event

from django.core.management.base import BaseCommand

from console_project.workers import (
    RUN_WORKER_LOCK_ID,
    hold_worker_session,
    stop_on_signals,
)
from runs.dispatch_control import start_control_cycle
from runs.services import run_control_tick


class Command(BaseCommand):
    help = "Coordinate central Jobs, start permissions, retries, and unresolved execution facts."

    def handle(self, *_args: object, **_options: object) -> None:
        stopEvent = Event()
        with (
            hold_worker_session(lockId=RUN_WORKER_LOCK_ID, workerName="Job control"),
            stop_on_signals(stopEvent),
        ):
            start_control_cycle()
            self.stdout.write("Job control worker started.")
            while not stopEvent.is_set():
                run_control_tick()
                stopEvent.wait(1)
