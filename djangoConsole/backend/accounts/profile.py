# FileName: profile.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.core.exceptions import PermissionDenied
from django.db import transaction

from operations.audit import get_audit_snapshot, record_audit

from organizations.permissions import (
    AccessChannel,
    get_current_membership,
    resolve_organization_access,
)

from .models import User


@transaction.atomic
def update_profile(
    *,
    actorId: uuid.UUID,
    channel: AccessChannel,
    username: str,
    timeZone: str,
) -> User:
    """Save the authenticated account's profile without changing identity or credentials."""
    if channel != AccessChannel.SESSION:
        raise PermissionDenied("A signed-in account is required to edit the profile.")

    # Resolve ownership on the server, then recheck it under the normal write locks.
    membership = get_current_membership(actorId=actorId)
    resolve_organization_access(
        actorId=actorId,
        organizationId=membership.organization_id,
        channel=channel,
        forUpdate=True,
    )
    # The authorization service already locked this account after its organization.
    user = User.objects.get(pk=actorId)
    dictAuditBefore = get_audit_snapshot(user)
    user.username = User.normalize_username(username.strip())
    user.time_zone = timeZone
    listExcludedFieldName = [
        modelField.name
        for modelField in user._meta.fields
        if modelField.name not in ("username", "time_zone")
    ]
    user.full_clean(
        exclude=listExcludedFieldName,
        validate_unique=False,
        validate_constraints=False,
    )
    # A profile save must never overwrite passwords, login timestamps, or account state.
    user.save(update_fields=["username", "time_zone"])
    record_audit(
        "account.update_profile",
        actorId=actorId,
        target=user,
        channel=channel,
        before=dictAuditBefore,
    )
    return user
