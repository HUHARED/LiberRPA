# FileName: urls.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.urls import path

from .views import asset_request

urlpatterns = [
    path("assets/", asset_request, {"action": "list"}, name="assets"),
    path("assets/<uuid:assetId>/", asset_request, {"action": "details"}, name="asset"),
    path(
        "assets/<uuid:assetId>/value/",
        asset_request,
        {"action": "value"},
        name="asset-value",
    ),
    path(
        "assets/<uuid:assetId>/deletion/",
        asset_request,
        {"action": "delete"},
        name="asset-deletion",
    ),
]
