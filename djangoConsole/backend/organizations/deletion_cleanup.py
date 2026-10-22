# FileName: deletion_cleanup.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from accounts.models import User, EditorSession
from executors.models import Executor, ExecutorSession, ExecutorGroup
from assets.models import Asset
from data_queues.models import DataQueue
from file_storage.models import StoredBlob
from shared_files.models import SharedFile, UploadSession
from packages.models import PackageUpload
from runs.models import JobRequest, RunLogUsage
from schedules.models import Schedule
from operations.audit_contracts import AuditAction
from operations.audit import record_audit
from operations.models import AuditScope, AuditRecord
from notifications.contracts import EmailStatus, EmailReasonCode
from notifications.models import EmailType, EmailDelivery

from .models import Organization, Membership, Department, MemberInvitation


@dataclass(frozen=True)
class OrganizationDeletionResult:
    organizationId: uuid.UUID
    deletedAccountCount: int
    queuedEmailCount: int


def _lock_organization_deliveries(organizationId: uuid.UUID) -> list[uuid.UUID]:
    """Lock delivery rows before the organization, matching the SMTP preparation order."""
    return list(
        EmailDelivery.objects
        .select_for_update(of=("self",))
        .filter(
            Q(invitation__organization_id=organizationId)
            | Q(run_reference__organization_id=organizationId)
            | Q(runrecipientverification__recipient__organization_id=organizationId)
        )
        .order_by("id")
        .values_list("id", flat=True)
    )


@transaction.atomic(durable=True)
def prepare_organization_execution_cleanup(organizationId: uuid.UUID) -> None:
    """Retire pending business mail before deleting its execution facts and references."""
    listDeliveryId = _lock_organization_deliveries(organizationId)
    organization = (
        Organization.objects.select_for_update().filter(pk=organizationId).first()
    )
    if organization is None:
        return
    if organization.deletion_started_at is None:
        raise ValidationError(
            "Organization cleanup has not started.", code="deletion_not_started"
        )
    EmailDelivery.objects.filter(
        pk__in=listDeliveryId, status=EmailStatus.PENDING
    ).update(
        status=EmailStatus.NOT_SENT,
        finished_at=timezone.now(),
        reason_code=EmailReasonCode.ORGANIZATION_DELETED,
    )
    # Schedule protects Package; assignments protect Executor; Jobs protect Department.
    Schedule.objects.filter(department__organization_id=organizationId).delete()
    JobRequest.objects.filter(organization_id=organizationId).delete()
    RunLogUsage.objects.filter(organization_id=organizationId).delete()


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
            AuditAction.ORGANIZATION_START_DELETION,
            actor=None,
            organization=organization,
            target=organization,
            scope=AuditScope.PLATFORM,
        )
    # A previous cleanup may have rolled back or stopped after committing this marker.
    return organization.id


@sensitive_variables()
@transaction.atomic(durable=True)
def complete_organization_deletion(
    organizationId: uuid.UUID,
) -> OrganizationDeletionResult | None:
    """Delete current organization data and queue completion notices in one commit.

    Only the standalone cleanup worker calls this after committing the start marker.
    Platform email outcomes and consumed SMTP budget survive organization deletion.
    """
    # NOTE: Match the email worker's delivery-before-organization lock order.
    # The committed start and business freeze prevent new invitation deliveries.
    listDeliveryId = _lock_organization_deliveries(organizationId)
    organization = (
        Organization.objects.select_for_update().filter(pk=organizationId).first()
    )
    if organization is None:
        return None
    if organization.deletion_started_at is None:
        raise ValidationError(
            "Organization cleanup has not started.", code="deletion_not_started"
        )

    if StoredBlob.objects.filter(organization_id=organizationId).exists():
        raise ValidationError(
            "Stored file cleanup is still pending.", code="storage_cleanup_pending"
        )
    SharedFile.objects.filter(department__organization_id=organizationId).delete()
    UploadSession.objects.filter(organization_id=organizationId).delete()
    PackageUpload.objects.filter(organization_id=organizationId).delete()

    strOrganizationName = organization.name
    strTimeZone = organization.default_time_zone
    listAccount = list(
        Membership.objects
        .filter(organization_id=organizationId, user__is_platform_admin=False)
        .order_by("user_id")
        .values_list("user_id", "user__email")
    )
    # Keep attempted deliveries, including Sending records whose SMTP result may still arrive.
    deliveries = EmailDelivery.objects.filter(pk__in=listDeliveryId)
    deliveries.filter(status=EmailStatus.PENDING).update(
        status=EmailStatus.NOT_SENT,
        finished_at=timezone.now(),
        reason_code=EmailReasonCode.ORGANIZATION_DELETED,
    )
    deliveries.update(invitation=None)
    MemberInvitation.objects.filter(organization_id=organizationId).delete()
    # Remove pending logins and associations before deleting their logical records.
    ExecutorSession.objects.filter(organization_id=organizationId).delete()
    EditorSession.objects.filter(organization_id=organizationId).delete()
    # Group deletion cascades memberships before their protected Executor references are removed.
    ExecutorGroup.objects.filter(department__organization_id=organizationId).delete()
    # Delete current and historical Executor identities before their protected departments.
    Executor.objects.filter(department__organization_id=organizationId).delete()
    Asset.objects.filter(department__organization_id=organizationId).delete()
    DataQueue.objects.filter(department__organization_id=organizationId).delete()
    # Account deletion cascades memberships, department roles, API keys, and private recovery/change proofs.
    User.objects.filter(pk__in=[userId for userId, _strEmail in listAccount]).delete()
    Membership.objects.filter(organization_id=organizationId).delete()
    _delete_organization_departments(organizationId)
    AuditRecord.objects.filter(
        scope=AuditScope.ORGANIZATION, organization_id=organizationId
    ).delete()
    record_audit(
        AuditAction.ORGANIZATION_COMPLETE_DELETION,
        actor=None,
        organization=organization,
        target=organization,
        scope=AuditScope.PLATFORM,
    )
    organization.delete()

    completedAt = timezone.now()
    listDelivery = EmailDelivery.objects.bulk_create([
        EmailDelivery(
            organization_id=organizationId,
            organization_name=strOrganizationName,
            time_zone=strTimeZone,
            email_type=EmailType.ORGANIZATION_DELETION_NOTICE,
            recipient=strEmail,
            created_at=completedAt,
        )
        for _userId, strEmail in listAccount
    ])
    # Notice rows become visible only when the deletion itself commits successfully.
    return OrganizationDeletionResult(
        organizationId=organizationId,
        deletedAccountCount=len(listAccount),
        queuedEmailCount=len(listDelivery),
    )
