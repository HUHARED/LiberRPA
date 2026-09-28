# FileName: urls.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.urls import path

from .views import (
    list_or_create_assets,
    get_or_update_asset,
    set_asset_value,
    delete_asset_view,
)

urlpatterns = [
    path("assets/", list_or_create_assets, name="assets"),
    path("assets/<uuid:assetId>/", get_or_update_asset, name="asset"),
    path("assets/<uuid:assetId>/value/", set_asset_value, name="asset-value"),
    path("assets/<uuid:assetId>/deletion/", delete_asset_view, name="asset-deletion"),
]
