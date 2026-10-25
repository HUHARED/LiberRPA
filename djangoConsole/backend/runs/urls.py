# FileName: urls.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.urls import path

from .views import (
    list_or_create_jobs,
    job_detail,
    update_job,
    list_runs,
    current_runs,
    run_statistics,
    run_selection,
    history_departments,
    run_detail,
    stop_run,
    rerun_options,
)
from .logs import clear_logs, list_logs, upload_logs
from .transfers import create_file_transfer, set_file_ready
from .executor_views import executor_work_endpoint

urlpatterns = [
    path("jobs/", list_or_create_jobs, name="jobs"),
    path("jobs/<uuid:workId>/", job_detail, name="job"),
    path("jobs/<uuid:workId>/control/", update_job, name="job-control"),
    path("runs/", list_runs, name="runs"),
    path("runs/current/", current_runs, name="current-runs"),
    path("runs/statistics/", run_statistics, name="run-statistics"),
    path("runs/selection/", run_selection, name="run-selection"),
    path("runs/departments/", history_departments, name="run-history-departments"),
    path("runs/clear-logs/", clear_logs, name="run-clear-logs"),
    path("runs/<uuid:workId>/", run_detail, name="run"),
    path("runs/<uuid:workId>/stop/", stop_run, name="run-stop"),
    path("runs/<uuid:workId>/rerun/", rerun_options, name="run-rerun"),
    path("runs/<uuid:runId>/logs/", list_logs, name="run-logs"),
    path("runs/<uuid:runId>/files/", create_file_transfer, name="run-file-transfer"),
    path(
        "clients/executor/work/poll/",
        executor_work_endpoint,
        {"action": "poll"},
        name="executor-work-poll",
    ),
    path(
        "clients/executor/work/permit/",
        executor_work_endpoint,
        {"action": "permit"},
        name="executor-work-permit",
    ),
    path(
        "clients/executor/work/events/",
        executor_work_endpoint,
        {"action": "events"},
        name="executor-work-events",
    ),
    path(
        "clients/executor/runs/<uuid:runId>/logs/",
        upload_logs,
        name="executor-run-logs",
    ),
    path(
        "clients/executor/file-transfers/<uuid:transferId>/ready/",
        set_file_ready,
        name="executor-file-transfer-ready",
    ),
]
