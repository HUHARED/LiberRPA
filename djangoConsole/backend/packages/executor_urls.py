# FileName: executor_urls.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.urls import path
from organizations.permissions import AccessChannel

from . import views
from .http import package_view

urlpatterns = [
    path(
        "preparations/<uuid:preparationId>/complete/",
        package_view(views.preparation_result, channel=AccessChannel.EXECUTOR),
    ),
    path(
        "<uuid:packageId>/downloads/",
        package_view(views.start_download, channel=AccessChannel.EXECUTOR),
    ),
    path(
        "downloads/<uuid:transferId>/content/",
        package_view(views.download_content, channel=AccessChannel.EXECUTOR),
    ),
]
