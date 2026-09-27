# FileName: services.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from typing import cast

from cryptography.fernet import MultiFernet
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from console_project.config import LimitsConfig
from console_project.contracts import JsonValue
from operations.audit import get_audit_snapshot, record_audit
from organizations.models import DepartmentRole
from organizations.permissions import (
    OrganizationAccessContext,
    get_authorized_departments,
)

from .models import Asset, SECRET_ASSET_TYPES
from .values import serialize_asset_value


class SecretStorageUnavailableError(Exception):
    pass


def _get_asset_for_write(
    access: OrganizationAccessContext, assetId: uuid.UUID, *, valueOnly: bool = False
) -> Asset:
    asset = Asset.objects.get(
        pk=assetId,
        department__in=get_authorized_departments(
            access, requiredRole=DepartmentRole.OPERATOR
        ),
    )
    if not valueOnly or asset.asset_type in SECRET_ASSET_TYPES:
        get_authorized_departments(access, requiredRole=DepartmentRole.DEVELOPER).get(
            pk=asset.department_id
        )
    return asset


@sensitive_variables()
def _set_asset_value(asset: Asset, value: JsonValue) -> None:
    strJson = serialize_asset_value(asset.asset_type, value)
    if asset.asset_type in SECRET_ASSET_TYPES:
        cipher = cast(MultiFernet | None, settings.CONSOLE_SECRET_CIPHER)
        if cipher is None:
            raise SecretStorageUnavailableError()
        asset.encrypted_value = cipher.encrypt(strJson.encode("utf-8")).decode("ascii")
        asset.value_json = ""
    else:
        asset.value_json = strJson
        asset.encrypted_value = ""


def _validate_asset_details(asset: Asset) -> None:
    try:
        asset.full_clean(exclude=["value_json", "encrypted_value"])
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
    _validate_asset_details(asset)
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
def update_asset_details(
    access: OrganizationAccessContext, assetId: uuid.UUID, *, name: str, notes: str
) -> Asset:
    asset = _get_asset_for_write(access, assetId)
    dictBefore = get_audit_snapshot(asset)
    asset.name = name
    asset.notes = notes
    _validate_asset_details(asset)
    if dictBefore == get_audit_snapshot(asset):
        return asset
    asset.updated_at = timezone.now()
    asset.save(update_fields=["name", "notes", "updated_at"])
    record_audit(
        "asset.update",
        actor=access.actor,
        organization=access.organization,
        target=asset,
        channel=access.channel,
        before=dictBefore,
    )
    return asset


@sensitive_variables()
def update_asset_value(
    access: OrganizationAccessContext, assetId: uuid.UUID, *, value: JsonValue
) -> Asset:
    asset = _get_asset_for_write(access, assetId, valueOnly=True)
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
    asset = _get_asset_for_write(access, assetId)
    # TODO: Show authorized Package/Schedule bindings as warnings when those models exist; do not block deletion.
    record_audit(
        "asset.delete",
        actor=access.actor,
        organization=access.organization,
        target=asset,
        channel=access.channel,
    )
    asset.delete()
