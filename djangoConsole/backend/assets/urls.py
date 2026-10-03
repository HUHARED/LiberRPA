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
from . import public_views

urlpatterns = [
    path("assets/", list_or_create_assets, name="assets"),
    path("assets/<uuid:assetId>/", get_or_update_asset, name="asset"),
    path("assets/<uuid:assetId>/value/", set_asset_value, name="asset-value"),
    path("assets/<uuid:assetId>/deletion/", delete_asset_view, name="asset-deletion"),
    path(
        "v1/assets/get_value/", public_views.get_asset_value, name="api-asset-get-value"
    ),
    path(
        "v1/assets/set_value/", public_views.set_asset_value, name="api-asset-set-value"
    ),
    path(
        "v1/assets/get_secret_text/",
        public_views.get_asset_secret_text,
        name="api-asset-get-secret-text",
    ),
    path(
        "v1/assets/get_credential/",
        public_views.get_asset_credential,
        name="api-asset-get-credential",
    ),
]
