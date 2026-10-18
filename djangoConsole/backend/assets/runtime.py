# FileName: runtime.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import json
import uuid
from typing import cast

from cryptography.fernet import InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.views.decorators.debug import sensitive_variables

from console_project.contracts import JsonValue
from organizations.department_queries import get_department_tree, resolve_department_path
from organizations.permissions import AccessChannel, OrganizationAccessContext
from organizations.validators import get_path_name_key

from .contracts import (
    AssetType,
    SECRET_ASSET_TYPES,
    AssetRuntimeValueResponse,
    AssetCredentialResponse,
)
from .models import Asset
from .queries import get_asset_query
from .services import SecretStorageUnavailableError, save_asset_value


class AssetRuntimeError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _resolve_asset_path(
    access: OrganizationAccessContext, assetPathParts: tuple[str, ...]
) -> Asset:
    dictDepartmentById = get_department_tree(access.organization.pk)
    department = resolve_department_path(assetPathParts[:-1], dictDepartmentById)
    return get_asset_query(access).get(
        department_id=department.pk, name_key=get_path_name_key(assetPathParts[-1])
    )


def _validate_ordinary_asset_type(asset: Asset) -> None:
    if asset.asset_type in SECRET_ASSET_TYPES:
        raise AssetRuntimeError(
            "asset_type_mismatch",
            "Use the dedicated function for this secret asset type.",
        )


@sensitive_variables()
def get_runtime_asset_value(
    access: OrganizationAccessContext, assetPathParts: tuple[str, ...]
) -> AssetRuntimeValueResponse:
    asset = _resolve_asset_path(access, assetPathParts)
    _validate_ordinary_asset_type(asset)
    return AssetRuntimeValueResponse(value=json.loads(asset.value_json))


@sensitive_variables()
def set_runtime_asset_value(
    access: OrganizationAccessContext,
    assetPathParts: tuple[str, ...],
    value: JsonValue,
    *,
    apiKeyId: uuid.UUID | None = None,
) -> AssetRuntimeValueResponse:
    asset = _resolve_asset_path(access, assetPathParts)
    _validate_ordinary_asset_type(asset)
    save_asset_value(access, asset, value=value, apiKeyId=apiKeyId)
    return AssetRuntimeValueResponse(value=value)


@sensitive_variables()
def get_runtime_secret_value(
    access: OrganizationAccessContext,
    assetPathParts: tuple[str, ...],
    assetType: AssetType,
) -> AssetRuntimeValueResponse | AssetCredentialResponse:
    if access.channel not in (AccessChannel.EDITOR, AccessChannel.EXECUTOR):
        raise PermissionDenied("Only native sessions can read secret assets.")
    asset = _resolve_asset_path(access, assetPathParts)
    if asset.asset_type != assetType:
        raise AssetRuntimeError(
            "asset_type_mismatch", "Use the function matching the asset's type."
        )
    cipher = cast(MultiFernet | None, settings.CONSOLE_SECRET_CIPHER)
    if cipher is None:
        raise SecretStorageUnavailableError()
    try:
        secretValue = json.loads(cipher.decrypt(asset.encrypted_value.encode("ascii")))
    except InvalidToken:
        raise SecretStorageUnavailableError() from None
    if assetType == AssetType.CREDENTIAL:
        return AssetCredentialResponse.model_validate(secretValue)
    return AssetRuntimeValueResponse(value=secretValue)
