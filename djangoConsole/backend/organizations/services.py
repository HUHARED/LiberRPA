# FileName: services.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from typing import cast

from django.conf import settings
from django.core.exceptions import ValidationError

from console_project.config import LimitsConfig
from operations.contracts import AuditAction
from operations.audit import get_audit_snapshot, record_audit

from .models import Organization
from .permissions import OrganizationAccessContext, require_organization_admin


def get_organization_settings(*, access: OrganizationAccessContext) -> Organization:
    """Read General settings using the current organization administrator permission."""
    require_organization_admin(access)
    return access.organization


def update_organization_settings(
    *,
    access: OrganizationAccessContext,
    name: str,
    defaultTimeZone: str,
    notes: str,
) -> Organization:
    """Save General settings using rechecked access in the caller's write transaction."""
    require_organization_admin(access)
    organization = access.organization
    dictAuditBefore = get_audit_snapshot(organization)
    organization.name = name.strip()
    organization.default_time_zone = defaultTimeZone
    organization.notes = notes
    listExcludedFieldName = [
        modelField.name
        for modelField in organization._meta.fields
        if modelField.name not in ("name", "default_time_zone", "notes")
    ]
    organization.full_clean(
        exclude=listExcludedFieldName,
        validate_unique=False,
        validate_constraints=False,
    )
    # Members keep their independent time zones; only future defaults use this setting.
    organization.save(update_fields=["name", "default_time_zone", "notes"])
    record_audit(
        AuditAction.ORGANIZATION_UPDATE,
        actor=access.actor,
        organization=organization,
        target=organization,
        channel=access.channel,
        before=dictAuditBefore,
    )
    return organization


def update_organization_retention(
    *, access: OrganizationAccessContext, runLogDays: int
) -> None:
    """Save log retention using the caller's locked organization and current session."""
    require_organization_admin(access)
    intMaximum = cast(LimitsConfig, settings.CONSOLE_LIMITS).runLogRetentionDays
    if not 1 <= runLogDays <= intMaximum:
        raise ValidationError({
            "run_log_days": f"Enter a whole number from 1 to {intMaximum}."
        })
    organization = access.organization
    if organization.run_log_retention_days == runLogDays:
        return

    dictAuditBefore = get_audit_snapshot(organization)
    organization.run_log_retention_days = runLogDays
    organization.save(update_fields=["run_log_retention_days"])
    record_audit(
        AuditAction.ORGANIZATION_UPDATE_RETENTION,
        actor=access.actor,
        organization=organization,
        target=organization,
        channel=access.channel,
        before=dictAuditBefore,
    )
