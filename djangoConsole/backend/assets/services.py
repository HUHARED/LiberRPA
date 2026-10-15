# FileName: services.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import json
import uuid
from typing import cast

from cryptography.fernet import MultiFernet
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from console_project.config import LimitsConfig
from console_project.contracts import JsonValue
from console_project.validators import validate_json_value
from operations.audit import get_audit_snapshot, record_audit
from organizations.models import DepartmentRole
from organizations.validators import get_path_name_key, normalize_path_name
from organizations.permissions import (
    OrganizationAccessContext,
    get_authorized_departments,
)

from .contracts import AssetUpdateRequest
from .models import AssetType, SECRET_ASSET_TYPES, Asset
from .queries import get_asset_query


class SecretStorageUnavailableError(Exception):
    pass


@sensitive_variables()
def _set_asset_value(asset: Asset, value: JsonValue) -> None:
    try:
        match asset.asset_type:
            case AssetType.TEXT | AssetType.SECRET_TEXT:
                if not isinstance(value, str):
                    raise ValueError("Enter a text value.")
            case AssetType.INTEGER:
                if type(value) is not int:
                    raise ValueError("Enter an integer.")
            case AssetType.NUMBER:
                if type(value) not in (int, float):
                    raise ValueError("Enter a number.")
            case AssetType.BOOLEAN:
                if type(value) is not bool:
                    raise ValueError("Select true or false.")
            case AssetType.CREDENTIAL:
                if (
                    not isinstance(value, dict)
                    or set(value) != {"username", "password"}
                    or not all(isinstance(part, str) for part in value.values())
                ):
                    raise ValueError(
                        "Provide the complete Username and Password as text."
                    )
            case AssetType.JSON:
                pass
            case _:
                raise ValueError("Select a supported asset type.")
        validate_json_value(value)
        strJson = json.dumps(
            value, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
        limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
        intLimit = (
            limits.maxSecretAssetValueBytes
            if asset.asset_type in SECRET_ASSET_TYPES
            else limits.maxAssetValueBytes
        )
        intValueBytes = len(
            (value if isinstance(value, str) else strJson).encode("utf-8")
        )
        if intValueBytes > intLimit:
            raise ValueError(f"The value exceeds the {intLimit}-byte UTF-8 limit.")
    except (ValueError, RecursionError) as e:
        raise ValidationError({
            "value": str(e)
            if not isinstance(e, (UnicodeError, RecursionError))
            else "Enter valid Unicode JSON within 64 levels of nesting."
        }) from None

    if asset.asset_type in SECRET_ASSET_TYPES:
        cipher = cast(MultiFernet | None, settings.CONSOLE_SECRET_CIPHER)
        if cipher is None:
            raise SecretStorageUnavailableError()
        asset.encrypted_value = cipher.encrypt(strJson.encode("utf-8")).decode("ascii")
        asset.value_json = ""
    else:
        asset.value_json = strJson
        asset.encrypted_value = ""


def _prepare_asset_details(asset: Asset) -> None:
    try:
        asset.name = normalize_path_name(asset.name)
    except ValidationError as e:
        raise ValidationError({"name": e}) from None
    asset.name_key = get_path_name_key(asset.name)
    try:
        asset.full_clean(exclude=["name", "value_json", "encrypted_value"])
    except ValidationError as e:
        if "__all__" in e.message_dict and any(
            error.code == "duplicate_asset_name" for error in e.error_dict["__all__"]
        ):
            raise ValidationError({
                "name": ValidationError(
                    "An asset with this name already exists in this department.",
                    code="duplicate_asset_name",
                )
            }) from None
        raise


@sensitive_variables()
def create_asset(
    access: OrganizationAccessContext,
    *,
    departmentId: uuid.UUID,
    name: str,
    notes: str,
    assetType: str,
    value: JsonValue,
) -> Asset:
    """The caller owns the organization/account locks and the enclosing transaction."""
    department = get_authorized_departments(
        access, requiredRole=DepartmentRole.DEVELOPER
    ).get(pk=departmentId)
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    if (
        Asset.objects.filter(department__organization=access.organization).count()
        >= limits.maxAssetsPerOrganization
    ):
        raise ValidationError(
            "This organization has reached its asset limit.", code="asset_count_limit"
        )
    asset = Asset(department=department, name=name, notes=notes, asset_type=assetType)
    _prepare_asset_details(asset)
    _set_asset_value(asset, value)
    asset.save(force_insert=True)
    record_audit(
        "asset.create",
        actor=access.actor,
        organization=access.organization,
        target=asset,
        channel=access.channel,
        before={},
    )
    return asset


@sensitive_variables()
def update_asset(
    access: OrganizationAccessContext, assetId: uuid.UUID, form: AssetUpdateRequest
) -> Asset:
    """The caller owns the organization/account locks and the enclosing transaction."""
    asset = get_asset_query(access).get(pk=assetId)
    boolSetValue = "value" in form.model_fields_set
    if form.details is not None or (
        boolSetValue and asset.asset_type in SECRET_ASSET_TYPES
    ):
        get_authorized_departments(access, requiredRole=DepartmentRole.DEVELOPER).get(
            pk=asset.department_id
        )

    dictBefore = get_audit_snapshot(asset)
    if form.details is not None:
        asset.name = form.details.name
        asset.notes = form.details.notes
        _prepare_asset_details(asset)
    boolDetailsChanged = dictBefore != get_audit_snapshot(asset)
    listField = ["name", "name_key", "notes"] if boolDetailsChanged else []
    if boolSetValue:
        _set_asset_value(asset, form.value)
        listField.extend(["value_json", "encrypted_value"])
    if not listField:
        return asset

    asset.updated_at = timezone.now()
    asset.save(update_fields=[*listField, "updated_at"])
    if boolDetailsChanged:
        record_audit(
            "asset.update",
            actor=access.actor,
            organization=access.organization,
            target=asset,
            channel=access.channel,
            before=dictBefore,
        )
    if boolSetValue:
        # Keep values out of the audit trail, including ordinary values.
        record_audit(
            "asset.set_value",
            actor=access.actor,
            organization=access.organization,
            target=asset,
            channel=access.channel,
        )
    return asset


@sensitive_variables()
def save_asset_value(
    access: OrganizationAccessContext, asset: Asset, *, value: JsonValue
) -> Asset:
    """Save an asset already authorized for this write under the organization lock."""
    _set_asset_value(asset, value)
    asset.updated_at = timezone.now()
    asset.save(update_fields=["value_json", "encrypted_value", "updated_at"])
    # Record the operation without putting old or new ordinary/secret values into audit.
    record_audit(
        "asset.set_value",
        actor=access.actor,
        organization=access.organization,
        target=asset,
        channel=access.channel,
    )
    return asset


def delete_asset(access: OrganizationAccessContext, assetId: uuid.UUID) -> None:
    asset = get_asset_query(access, requiredRole=DepartmentRole.DEVELOPER).get(pk=assetId)
    # The details response reports known bindings; confirmed deletion leaves their configuration unchanged.
    record_audit(
        "asset.delete",
        actor=access.actor,
        organization=access.organization,
        target=asset,
        channel=access.channel,
    )
    asset.delete()
