# FileName: profile.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.core.exceptions import PermissionDenied

from operations.audit_contracts import AuditAction
from operations.audit import get_audit_snapshot, record_audit
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
)

from .models import User


def update_profile(
    *,
    access: OrganizationAccessContext,
    username: str,
    timeZone: str,
) -> User:
    """Save the profile using rechecked session access in the caller's write transaction."""
    if access.channel != AccessChannel.SESSION:
        raise PermissionDenied("A signed-in account is required to edit the profile.")

    user = access.actor
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
        AuditAction.ACCOUNT_UPDATE_PROFILE,
        actor=user,
        organization=access.organization,
        target=user,
        channel=access.channel,
        before=dictAuditBefore,
    )
    return user
