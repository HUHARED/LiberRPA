# FileName: lifecycle.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from .models import Organization
from .permissions import (
    AccessChannel,
    lock_organization_for_deletion,
    require_organization_business_available,
)

_ORGANIZATION_DELETION_DELAY = timedelta(days=7)


@sensitive_variables()
@transaction.atomic
def schedule_organization_deletion(
    *,
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    currentPassword: str,
) -> Organization:
    """Freeze an available organization after verifying the current administrator's password.

    actorId and channel come from verified credentials, never from the request body.
    This operation schedules cleanup without deleting accounts or organization resources.
    """
    organization, actor = lock_organization_for_deletion(
        actorId=actorId, organizationId=organizationId, channel=channel
    )
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

    # Reuse the account locked during authorization, including its current password hash.
    if not actor.check_password(currentPassword):
        raise ValidationError({
            "current_password": ValidationError(
                "The current password is incorrect.", code="incorrect_password"
            )
        })

    # Start the waiting period after authorization and password verification succeed.
    requestedAt = timezone.now()
    organization.deletion_requested_at = requestedAt
    organization.deletion_due_at = requestedAt + _ORGANIZATION_DELETION_DELAY
    organization.save(update_fields=["deletion_requested_at", "deletion_due_at"])
    return organization


@transaction.atomic
def cancel_organization_deletion(
    *, actorId: uuid.UUID, organizationId: uuid.UUID, channel: AccessChannel
) -> Organization:
    """Allow any current active administrator to cancel before cleanup actually starts.

    No password is required, and an independent service suspension remains in place.
    A future cleanup worker must take the same organization lock before marking its start.
    """
    organization, _ = lock_organization_for_deletion(
        actorId=actorId, organizationId=organizationId, channel=channel
    )
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
    organization.deletion_requested_at = None
    organization.deletion_due_at = None
    organization.save(update_fields=["deletion_requested_at", "deletion_due_at"])
    return organization
