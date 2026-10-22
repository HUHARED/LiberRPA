# FileName: asgi.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import os
from typing import cast

from asgiref.typing import ASGI3Application
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "console_project.settings")

djangoApplication = get_asgi_application()

from runs.transfers import RunFileRelay
from runs.executor_socket import ExecutorControl
from accounts.browser_socket import BrowserSocket

# Django and asgiref use different type annotations for the same ASGI interface.
application = BrowserSocket(
    ExecutorControl(RunFileRelay(cast(ASGI3Application, djangoApplication)))
)
