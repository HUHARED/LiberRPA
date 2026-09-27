# FileName: urls.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.urls import path

from .views import file_request, public_file_request

urlpatterns = []
for prefix, view, namePrefix in (
    ("shared-files/", file_request, "shared-files"),
    ("v1/shared-files/", public_file_request, "public-shared-files"),
):
    for suffix, action in (
        ("list/", "list"),
        ("query/", "query"),
        ("deletion/", "delete"),
        ("uploads/", "upload"),
        ("uploads/<uuid:transferId>/", "status"),
        ("uploads/<uuid:transferId>/chunks/<int:offset>/", "chunk"),
        ("uploads/<uuid:transferId>/complete/", "complete"),
        ("uploads/<uuid:transferId>/cancel/", "cancel"),
        ("downloads/", "download"),
        ("downloads/<uuid:transferId>/", "content"),
    ):
        urlpatterns.append(
            path(prefix + suffix, view, {"action": action}, name=f"{namePrefix}-{action}")
        )
