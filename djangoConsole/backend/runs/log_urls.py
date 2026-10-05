# FileName: log_urls.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.urls import path

from .logs import clear_logs, list_logs, upload_logs
from .transfers import create_file_transfer, set_file_ready

urlpatterns = [
    path("runs/clear-logs/", clear_logs),
    path("runs/<uuid:runId>/logs/", list_logs),
    path("runs/<uuid:runId>/files/", create_file_transfer),
    path("clients/executor/runs/<uuid:runId>/logs/", upload_logs),
    path("clients/executor/file-transfers/<uuid:transferId>/ready/", set_file_ready),
]
