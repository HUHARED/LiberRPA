# FileName: restore.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from datetime import datetime

from django.apps import apps
from django.contrib.sessions.models import Session
from django.core.exceptions import ImproperlyConfigured
from django.db import connection, transaction
from django.db.models import Exists, F, OuterRef, Q, Value
from django.db.models.functions import Greatest
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.state import ProjectState

from accounts.models import (
    User,
    EditorSession,
    ApiKey,
    RegistrationToken,
    PasswordResetRequest,
    EmailChangeRequest,
)
from organizations.models import MemberInvitation
from executors.models import ExecutorSession
from packages.contracts import PackageUploadState
from packages.models import PackageUpload, PackagePreparation
from shared_files.contracts import UploadState
from shared_files.models import UploadSession
from file_storage.models import StoredBlobState, StoredBlob, DownloadSession
from schedules.models import SchedulerState
from runs.contracts import JobState, AssignmentState
from runs.models import Job, ExecutorWorkState, Assignment, Run, RunFileTransfer, DispatchControl
from notifications.contracts import EmailStatus, EmailReasonCode
from notifications.models import (
    EmailWorkerState,
    EmailDelivery,
    RunEmailRecipient,
    RunRecipientVerification,
)

from .backup import BackupManifest
from .backup_models import BackupState, BackupRecord
from .contracts import AuditChannel
from .models import MaintenanceState, CleanupState, AuditScope
from .audit import record_audit

_STR_RESTORE_REASON = (
    "Console was restored from a backup. Previous work will not resume; "
    "check any execution that may still be active on the Executor."
)


def validate_restored_schema(manifest: BackupManifest) -> None:
    """Require the matching schema; restoring a backup never runs migrations."""
    loader = MigrationLoader(connection)
    if set(loader.applied_migrations) != set(manifest.migrations):
        raise ImproperlyConfigured("The restored migration history differs from the backup.")
    loader.check_consistent_history(connection)
    if set(loader.graph.nodes) - set(loader.applied_migrations):
        raise ImproperlyConfigured("Use the Console release matching this backup's migrations.")
    if MigrationAutodetector(
        loader.project_state(), ProjectState.from_apps(apps)
    ).changes(graph=loader.graph):
        raise ImproperlyConfigured("The current models do not match the restored schema.")


@transaction.atomic
def sanitize_restored_database(manifest: BackupManifest, restoredAt: datetime) -> None:
    """Invalidate old authority and pending actions without inventing execution outcomes."""
    setBlobId = set(manifest.blob_ids)
    if set(
        StoredBlob.objects.filter(state=StoredBlobState.AVAILABLE).values_list("pk", flat=True)
    ) != setBlobId:
        raise ImproperlyConfigured("The restored files do not match the database snapshot.")

    User.objects.update(session_version=F("session_version") + 1)
    Session.objects.all().delete()
    EditorSession.objects.all().delete()
    ExecutorSession.objects.all().delete()
    ApiKey.objects.filter(revoked_at__isnull=True).update(revoked_at=restoredAt)
    RegistrationToken.objects.all().delete()
    PasswordResetRequest.objects.all().delete()
    EmailChangeRequest.objects.all().delete()
    MemberInvitation.objects.filter(accepted_at__isnull=True).update(
        token_hash=None, revoked_at=restoredAt
    )
    RunEmailRecipient.objects.update(verification_id=uuid.uuid4())
    RunRecipientVerification.objects.all().delete()

    # A restored sending attempt may have reached SMTP after the snapshot; do not resend it.
    EmailDelivery.objects.filter(status=EmailStatus.PENDING).update(
        status=EmailStatus.NOT_SENT,
        finished_at=Greatest(Value(restoredAt), F("created_at")),
        reason_code=EmailReasonCode.INSTANCE_RESTORED,
    )
    EmailDelivery.objects.filter(status=EmailStatus.SENDING).update(
        status=EmailStatus.UNKNOWN,
        finished_at=Greatest(Value(restoredAt), F("created_at"), F("attempted_at")),
        reason_code=EmailReasonCode.INSTANCE_RESTORED,
    )

    Assignment.objects.filter(state=AssignmentState.PREPARING).update(
        state=AssignmentState.WITHDRAWN, reason=_STR_RESTORE_REASON
    )
    Assignment.objects.filter(
        state__in=(
            AssignmentState.PERMITTED,
            AssignmentState.RUNNING,
            AssignmentState.NEEDS_REVIEW,
        )
    ).update(state=AssignmentState.NEEDS_REVIEW, reason=_STR_RESTORE_REASON)
    jobs = Job.objects.exclude(state=JobState.FINISHED)
    jobs.update(source_access_revoked_at=restoredAt, retry_at=None)
    jobs = jobs.alias(
        unknown_assignment=Exists(
            Assignment.objects.filter(job_id=OuterRef("pk"), state=AssignmentState.NEEDS_REVIEW)
        ),
        unknown_run=Exists(Run.objects.filter(job_id=OuterRef("pk"), ended_at__isnull=True)),
    )
    unknownWork = (
        Q(unknown_assignment=True)
        | Q(unknown_run=True)
        | Q(state=JobState.NEEDS_REVIEW)
    )
    jobs.filter(unknownWork).update(state=JobState.NEEDS_REVIEW, reason=_STR_RESTORE_REASON)
    jobs.exclude(unknownWork).update(
        state=JobState.FINISHED, ended_at=restoredAt, reason=_STR_RESTORE_REASON
    )
    ExecutorWorkState.objects.all().delete()
    PackagePreparation.objects.all().delete()
    DispatchControl.objects.all().delete()
    SchedulerState.objects.update_or_create(pk=1, defaults={"scanned_at": restoredAt})

    # Temporary transfers are not backed up; receipts remain terminal rather than resuming.
    DownloadSession.objects.all().delete()
    RunFileTransfer.objects.all().delete()
    PackageUpload.objects.filter(state=PackageUploadState.RECEIVING).update(
        state=PackageUploadState.CANCELED, expires_at=restoredAt
    )
    UploadSession.objects.filter(state=UploadState.RECEIVING).update(
        state=UploadState.CANCELED, expires_at=restoredAt
    )
    StoredBlob.objects.exclude(pk__in=setBlobId).delete()

    EmailWorkerState.objects.all().delete()
    CleanupState.objects.all().delete()
    BackupRecord.objects.all().delete()
    BackupState.objects.all().delete()
    maintenanceState, _ = MaintenanceState.objects.update_or_create(
        pk=1, defaults={"entered_at": restoredAt}
    )
    record_audit(
        "backup.restore",
        actor=None,
        organization=None,
        target=maintenanceState,
        channel=AuditChannel.SYSTEM,
        scope=AuditScope.PLATFORM,
        metadata={"backup_id": str(manifest.backup_id), "data_as_of": manifest.data_as_of},
    )
