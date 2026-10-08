# FileName: urls.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.urls import path

from .protocol import executor_work_endpoint
from .views import work_endpoint

urlpatterns = [
    path("jobs/", work_endpoint, {"action": "jobs"}, name="jobs"),
    path("jobs/<uuid:workId>/", work_endpoint, {"action": "job"}, name="job"),
    path(
        "jobs/<uuid:workId>/control/",
        work_endpoint,
        {"action": "control"},
        name="job-control",
    ),
    path("runs/", work_endpoint, {"action": "runs"}, name="runs"),
    path(
        "runs/selection/",
        work_endpoint,
        {"action": "run-selection"},
        name="run-selection",
    ),
    path(
        "runs/departments/",
        work_endpoint,
        {"action": "departments"},
        name="run-history-departments",
    ),
    path("runs/<uuid:workId>/", work_endpoint, {"action": "run"}, name="run"),
    path("runs/<uuid:workId>/stop/", work_endpoint, {"action": "stop"}, name="run-stop"),
    path(
        "runs/<uuid:workId>/rerun/", work_endpoint, {"action": "rerun"}, name="run-rerun"
    ),
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
]
