# FileName: lifecycle.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from datetime import timedelta

from django.contrib.auth.hashers import check_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views.decorators.debug import sensitive_variables

from accounts.models import User
from accounts.session_revocation import SessionInvalidatedError
from operations.audit import get_audit_snapshot, record_audit

from .models import Organization
from .permissions import (
    AccessChannel,
    require_organization_business_available,
    lock_organization_for_deletion,
)

_ORGANIZATION_DELETION_DELAY = timedelta(days=7)


@sensitive_variables()
def _require_current_session(actor: User, sessionAuthHash: str) -> None:
    """Check the initiating session against the account locked for this transition."""
    if not sessionAuthHash or not constant_time_compare(
        sessionAuthHash, actor.get_session_auth_hash()
    ):
        raise SessionInvalidatedError("The current session is no longer valid.")


@sensitive_variables()
@transaction.atomic
def schedule_organization_deletion(
    *,
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    currentPassword: str,
    sessionAuthHash: str,
) -> Organization:
    """Freeze an available organization after verifying the current administrator's password.

    actorId, channel, and sessionAuthHash come from verified server-side authentication.
    This operation schedules cleanup without deleting accounts or organization resources.
    """
    organization, actor = lock_organization_for_deletion(
        actorId=actorId, organizationId=organizationId, channel=channel
    )
    _require_current_session(actor, sessionAuthHash)
    if organization.deletion_started_at is not None:
        raise ValidationError(
            "Organization deletion is already in progress.", code="deletion_in_progress"
        )
    if organization.deletion_requested_at is not None:
        raise ValidationError(
            "Organization deletion is already scheduled.",
            code="deletion_already_scheduled",
        )
    require_organization_business_available(organization)

    # Verify without a hash-upgrade setter so existing sessions remain available for cancellation.
    if not check_password(currentPassword, actor.password):
        raise ValidationError({
            "current_password": ValidationError(
                "The current password is incorrect.", code="incorrect_password"
            )
        })

    # Start the waiting period after authorization and password verification succeed.
    requestedAt = timezone.now()
    dictAuditBefore = get_audit_snapshot(organization)
    organization.deletion_requested_at = requestedAt
    organization.deletion_due_at = requestedAt + _ORGANIZATION_DELETION_DELAY
    organization.save(update_fields=["deletion_requested_at", "deletion_due_at"])
    record_audit(
        "organization.schedule_deletion",
        actor=actor,
        organization=organization,
        target=organization,
        channel=channel,
        before=dictAuditBefore,
    )
    return organization


@sensitive_variables()
@transaction.atomic
def cancel_organization_deletion(
    *,
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    sessionAuthHash: str,
) -> Organization:
    """Allow any current active administrator to cancel before cleanup actually starts.

    No password is required, and an independent service suspension remains in place.
    The cleanup worker takes the same organization lock before committing its start.
    """
    organization, actor = lock_organization_for_deletion(
        actorId=actorId, organizationId=organizationId, channel=channel
    )
    _require_current_session(actor, sessionAuthHash)
    if organization.deletion_started_at is not None:
        raise ValidationError(
            "Organization deletion can no longer be canceled.",
            code="deletion_in_progress",
        )
    if organization.deletion_requested_at is None:
        raise ValidationError(
            "Organization deletion is not scheduled.", code="deletion_not_scheduled"
        )

    # The due time does not close the cancellation window; the actual cleanup start does.
    dictAuditBefore = get_audit_snapshot(organization)
    organization.deletion_requested_at = None
    organization.deletion_due_at = None
    organization.save(update_fields=["deletion_requested_at", "deletion_due_at"])
    record_audit(
        "organization.cancel_deletion",
        actor=actor,
        organization=organization,
        target=organization,
        channel=channel,
        before=dictAuditBefore,
    )
    return organization
