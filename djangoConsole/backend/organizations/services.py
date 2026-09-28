# FileName: services.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.db import transaction

from operations.audit import get_audit_snapshot, record_audit

from .creation import OrganizationCreationResult, create_organization_records
from .department_services import create_department, update_department
from .member_services import update_membership
from .models import Organization
from .permissions import (
    AccessChannel,
    resolve_organization_access,
    require_organization_admin,
    lock_organization_admin_access,
)

# Preserve existing Python entry points; each implementation belongs to its domain module.
__all__ = [
    "OrganizationCreationResult",
    "create_organization_records",
    "create_department",
    "update_department",
    "update_membership",
    "get_organization_settings",
    "update_organization_settings",
]


def get_organization_settings(
    *, actorId: uuid.UUID, organizationId: uuid.UUID, channel: AccessChannel
) -> Organization:
    """Read General settings using the current organization administrator permission."""
    access = resolve_organization_access(
        actorId=actorId, organizationId=organizationId, channel=channel
    )
    require_organization_admin(access)
    return access.organization


@transaction.atomic
def update_organization_settings(
    *,
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    name: str,
    defaultTimeZone: str,
    notes: str,
) -> Organization:
    """Save the complete General form without changing members or service state."""
    access = lock_organization_admin_access(actorId, organizationId, channel)
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
        channel=channel,
        before=dictAuditBefore,
    )
    return organization
