# FileName: cleanup.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from accounts.models import User
from assets.models import Asset
from data_queues.models import DataQueue
from operations.audit import record_audit
from operations.models import AuditScope, AuditRecord
from executors.models import Executor, ExecutorGroup, ExecutorSession
from notifications.models import (
    EmailDelivery,
    EmailStatus,
    EmailType,
    OrganizationDeletionNotice,
)

from .models import Department, MemberInvitation, Membership, Organization


@dataclass(frozen=True)
class OrganizationDeletionResult:
    organizationId: uuid.UUID
    deletedAccountCount: int
    queuedEmailCount: int


@transaction.atomic(durable=True)
def start_next_organization_deletion() -> uuid.UUID | None:
    """Commit the irreversible start boundary while the caller owns the cleanup worker session."""
    organization = (
        Organization.objects
        .select_for_update(skip_locked=True)
        .filter(
            deletion_requested_at__isnull=False,
            deletion_due_at__lte=timezone.now(),
        )
        .order_by("deletion_due_at", "id")
        .first()
    )
    if organization is None:
        return None
    if organization.deletion_started_at is None:
        startedAt = timezone.now()
        if (
            organization.deletion_due_at is None
            or startedAt < organization.deletion_due_at
        ):
            return None
        organization.deletion_started_at = startedAt
        organization.save(update_fields=["deletion_started_at"])
        record_audit(
            "organization.start_deletion",
            actorId=None,
            organization=organization,
            target=organization,
            scope=AuditScope.PLATFORM,
        )
    # A previous cleanup may have rolled back or stopped after committing this marker.
    return organization.id


def _delete_organization_departments(organizationId: uuid.UUID) -> None:
    """Delete every department from leaves upward, including logically deleted departments."""
    departments = Department.objects.filter(organization_id=organizationId)
    while departments.exists():
        listLeafId = list(
            departments.filter(children__isnull=True).values_list("id", flat=True)
        )
        if not listLeafId:
            raise ValidationError(
                "The department hierarchy prevents organization cleanup.",
                code="department_cleanup_blocked",
            )
        departments.filter(pk__in=listLeafId).delete()


@sensitive_variables()
@transaction.atomic(durable=True)
def complete_organization_deletion(
    organizationId: uuid.UUID,
) -> OrganizationDeletionResult | None:
    """Delete current organization data and queue completion notices in one commit.

    Only the standalone cleanup worker calls this after committing the start marker.
    Platform email outcomes and consumed SMTP budget survive organization deletion.
    """
    # Match the email worker's delivery-before-organization lock order.
    # The committed start and business freeze prevent new invitation deliveries.
    listDeliveryId = list(
        EmailDelivery.objects
        .select_for_update(of=("self",))
        .filter(invitation__organization_id=organizationId)
        .order_by("id")
        .values_list("id", flat=True)
    )
    organization = (
        Organization.objects.select_for_update().filter(pk=organizationId).first()
    )
    if organization is None:
        return None
    if organization.deletion_started_at is None:
        raise ValidationError(
            "Organization cleanup has not started.", code="deletion_not_started"
        )

    organizationName = organization.name
    listAccount = list(
        Membership.objects
        .filter(organization_id=organizationId)
        .order_by("user_id")
        .values_list("user_id", "user__email")
    )
    # Keep attempted deliveries, including Sending records whose SMTP result may still arrive.
    deliveries = EmailDelivery.objects.filter(pk__in=listDeliveryId)
    deliveries.filter(status=EmailStatus.PENDING).update(
        status=EmailStatus.NOT_SENT,
        finished_at=timezone.now(),
        reason_code="organization_deleted",
    )
    deliveries.update(invitation=None)
    MemberInvitation.objects.filter(organization_id=organizationId).delete()
    # Remove pending logins and associations before deleting their logical records.
    ExecutorSession.objects.filter(organization_id=organizationId).delete()
    # Group deletion cascades memberships before their protected Executor references are removed.
    ExecutorGroup.objects.filter(department__organization_id=organizationId).delete()
    # Delete current and historical Executor identities before their protected departments.
    Executor.objects.filter(department__organization_id=organizationId).delete()
    Asset.objects.filter(department__organization_id=organizationId).delete()
    DataQueue.objects.filter(department__organization_id=organizationId).delete()
    # Account deletion cascades memberships, department roles, API keys, and private recovery/change proofs.
    User.objects.filter(pk__in=[userId for userId, _email in listAccount]).delete()
    _delete_organization_departments(organizationId)
    # TODO: Add cleanup for future resource models and stored files; queue completion notices only after every cleanup stage succeeds.
    AuditRecord.objects.filter(
        scope=AuditScope.ORGANIZATION, organization_id=organizationId
    ).delete()
    record_audit(
        "organization.complete_deletion",
        actorId=None,
        organization=organization,
        target=organization,
        scope=AuditScope.PLATFORM,
    )
    organization.delete()

    completedAt = timezone.now()
    listDelivery = EmailDelivery.objects.bulk_create([
        EmailDelivery(
            email_type=EmailType.ORGANIZATION_DELETION_NOTICE,
            recipient=email,
            created_at=completedAt,
        )
        for _userId, email in listAccount
    ])
    OrganizationDeletionNotice.objects.bulk_create([
        OrganizationDeletionNotice(
            delivery=delivery,
            organization_id=organizationId,
            organization_name=organizationName,
        )
        for delivery in listDelivery
    ])
    # Notice rows become visible only when the deletion itself commits successfully.
    return OrganizationDeletionResult(
        organizationId=organizationId,
        deletedAccountCount=len(listAccount),
        queuedEmailCount=len(listDelivery),
    )
