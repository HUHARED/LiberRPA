# FileName: urls.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.urls import path

from . import views
from .http import package_view

urlpatterns = [
    path("", package_view(views.list_packages)),
    path("departments/", package_view(views.list_departments)),
    path("options/", package_view(views.package_options)),
    path("uploads/", package_view(views.start_upload)),
    path("uploads/<uuid:uploadId>/", package_view(views.upload_detail)),
    path(
        "uploads/<uuid:uploadId>/chunks/<int:offset>/", package_view(views.upload_chunk)
    ),
    path("uploads/<uuid:uploadId>/complete/", package_view(views.finish_upload)),
    path("uploads/<uuid:uploadId>/cancel/", package_view(views.abort_upload)),
    path("downloads/<uuid:transferId>/content/", package_view(views.download_content)),
    path("<uuid:packageId>/", package_view(views.package_detail)),
    path("<uuid:packageId>/settings/", package_view(views.update_settings)),
    path("<uuid:packageId>/preparations/cancel/", package_view(views.cancel_preparation)),
    path("<uuid:packageId>/delete/", package_view(views.remove_package)),
    path("<uuid:packageId>/downloads/", package_view(views.start_download)),
]
