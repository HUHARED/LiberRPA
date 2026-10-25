# FileName: editor_urls.py
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
        "departments/",
        package_view(views.list_departments, channel=AccessChannel.EDITOR),
        name="editor-package-departments",
    ),
    path(
        "uploads/",
        package_view(views.start_upload, channel=AccessChannel.EDITOR),
        name="editor-package-upload",
    ),
    path(
        "uploads/<uuid:uploadId>/",
        package_view(views.upload_detail, channel=AccessChannel.EDITOR),
        name="editor-package-upload-status",
    ),
    path(
        "uploads/<uuid:uploadId>/chunks/<int:offset>/",
        package_view(views.upload_chunk, channel=AccessChannel.EDITOR),
        name="editor-package-upload-chunk",
    ),
    path(
        "uploads/<uuid:uploadId>/complete/",
        package_view(views.finish_upload, channel=AccessChannel.EDITOR),
        name="editor-package-upload-complete",
    ),
    path(
        "uploads/<uuid:uploadId>/cancel/",
        package_view(views.abort_upload, channel=AccessChannel.EDITOR),
        name="editor-package-upload-cancel",
    ),
]
