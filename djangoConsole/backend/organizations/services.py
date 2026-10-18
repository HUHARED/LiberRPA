# FileName: services.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from operations.audit import get_audit_snapshot, record_audit

from .models import Organization
from .permissions import (
    AccessChannel,
    OrganizationAccessContext,
    resolve_organization_access,
    require_organization_admin,
)


def get_organization_settings(
    *, actorId: uuid.UUID, organizationId: uuid.UUID, channel: AccessChannel
) -> Organization:
    """Read General settings using the current organization administrator permission."""
    access = resolve_organization_access(
        actorId=actorId, organizationId=organizationId, channel=channel
    )
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
        "organization.update",
        actor=access.actor,
        organization=organization,
        target=organization,
        channel=access.channel,
        before=dictAuditBefore,
    )
    return organization
