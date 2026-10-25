# FileName: urls.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.urls import path

from . import views
from .http import package_view

urlpatterns = [
    path(
        "project-groups/",
        package_view(views.list_package_project_groups),
        name="package-project-groups",
    ),
    path(
        "departments/",
        package_view(views.list_departments),
        name="package-departments",
    ),
    path("options/", package_view(views.package_options), name="package-options"),
    path("uploads/", package_view(views.start_upload), name="package-upload"),
    path(
        "uploads/<uuid:uploadId>/",
        package_view(views.upload_detail),
        name="package-upload-status",
    ),
    path(
        "uploads/<uuid:uploadId>/chunks/<int:offset>/",
        package_view(views.upload_chunk),
        name="package-upload-chunk",
    ),
    path(
        "uploads/<uuid:uploadId>/complete/",
        package_view(views.finish_upload),
        name="package-upload-complete",
    ),
    path(
        "uploads/<uuid:uploadId>/cancel/",
        package_view(views.abort_upload),
        name="package-upload-cancel",
    ),
    path(
        "downloads/<uuid:transferId>/content/",
        package_view(views.download_content),
        name="package-download-content",
    ),
    path(
        "<uuid:packageId>/project-packages/",
        package_view(views.list_project_packages),
        name="package-project-packages",
    ),
    path("<uuid:packageId>/", package_view(views.package_detail), name="package"),
    path(
        "<uuid:packageId>/settings/",
        package_view(views.update_settings),
        name="package-settings",
    ),
    path(
        "<uuid:packageId>/preparations/cancel/",
        package_view(views.cancel_preparation),
        name="package-preparation-cancel",
    ),
    path(
        "<uuid:packageId>/delete/",
        package_view(views.remove_package),
        name="package-delete",
    ),
    path(
        "<uuid:packageId>/downloads/",
        package_view(views.start_download),
        name="package-download",
    ),
]
