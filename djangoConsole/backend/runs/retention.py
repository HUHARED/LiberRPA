# FileName: retention.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from organizations.models import Organization
from notifications.models import EmailDelivery, EmailStatus, EmailReasonCode
from schedules.models import ScheduleTrigger

from .models import (
    JobState,
    AssignmentState,
    RunEventKind,
    JobRequest,
    Job,
    Assignment,
    Run,
    RunLog,
    RunFileTransfer,
    RunEvent,
)

_INT_RECEIPT_RETENTION_DAYS = 30


def prune_run_data(limit: int = 200) -> tuple[int, int]:
    """Clear only terminal Job groups; active and unresolved work stays protected."""
    intJobsRemoved = 0
    intLogsCleared = 0
    currentTime = timezone.now()
    limits = settings.CONSOLE_LIMITS
    receiptCutoff = currentTime - timedelta(days=_INT_RECEIPT_RETENTION_DAYS)
    historyCutoff = currentTime - timedelta(days=limits.runHistoryRetentionDays)
    for organizationId in Organization.objects.values_list("id", flat=True).iterator(
        chunk_size=100
    ):
        # Actual history and explicit Close use ordinary retention. No-Run receipts have their own window.
        terminalCandidates = (
            Job.objects
            .filter(request__organization_id=organizationId, state=JobState.FINISHED)
            .annotate(
                run_count=Count("runs"), retention_start=Coalesce("closed_at", "ended_at")
            )
            .filter(Q(run_count__gt=0) | Q(closed_at__isnull=False))
        )
        intExistingRuns = Run.objects.filter(
            job__request__organization_id=organizationId,
            job__state=JobState.FINISHED,
        ).count()
        if intExistingRuns <= limits.maxRunHistoryPerOrganization:
            terminalCandidates = terminalCandidates.filter(
                retention_start__lt=historyCutoff
            )
        else:
            terminalCandidates = terminalCandidates.filter(
                Q(run_count__gt=0) | Q(retention_start__lt=historyCutoff)
            )
        listCandidateJobId = list(
            terminalCandidates.order_by("retention_start", "id").values_list(
                "id", flat=True
            )[:limit]
        )
        # Terminal candidates cannot acquire new Run-email events; use delivery-before-organization lock order.
        with transaction.atomic():
            listPendingDeliveryId = list(
                EmailDelivery.objects
                .select_for_update(of=("self",))
                .filter(
                    status=EmailStatus.PENDING,
                    run_reference__run_id__in=Run.objects.filter(
                        job_id__in=listCandidateJobId
                    ).values("id"),
                )
                .order_by("id")
                .values_list("id", flat=True)
            )
            Organization.objects.select_for_update().get(pk=organizationId)
            logs = RunLog.objects.filter(
                run__job__request__organization_id=organizationId
            )
            intBytes = logs.aggregate(total=Sum("byte_count"))["total"] or 0
            intGroups = logs.values("run_id").distinct().count()
            terminalRuns = (
                Run.objects
                .filter(
                    job__request__organization_id=organizationId,
                    job__state=JobState.FINISHED,
                    logs_cleared_at__isnull=True,
                )
                .select_related("job")
                .order_by("job__ended_at", "started_at", "id")
            )
            for run in terminalRuns[:limit]:
                retentionStart = run.job.closed_at or run.job.ended_at
                if retentionStart is None:
                    continue
                boolOld = retentionStart < currentTime - timedelta(
                    days=limits.runLogRetentionDays
                )
                if (
                    not boolOld
                    and intBytes <= limits.maxRunLogBytesPerOrganization
                    and intGroups <= limits.maxRunLogGroupsPerOrganization
                ):
                    continue
                intRunBytes = run.logs.aggregate(total=Sum("byte_count"))["total"] or 0
                boolHasLogs = run.logs.exists()
                run.logs.all().delete()
                run.logs_cleared_at = currentTime
                run.save(update_fields=["logs_cleared_at"])
                intBytes -= intRunBytes
                intGroups -= int(boolHasLogs)
                intLogsCleared += 1
            terminalJobs = (
                Job.objects
                .filter(request__organization_id=organizationId, state=JobState.FINISHED)
                .annotate(run_count=Count("runs"))
                .filter(Q(run_count__gt=0) | Q(closed_at__isnull=False))
                .order_by("ended_at", "id")
            )
            intRuns = Run.objects.filter(
                job__request__organization_id=organizationId,
                job__state=JobState.FINISHED,
            ).count()
            for jobId, closedAt, endedAt, intRunCount in terminalJobs.filter(
                pk__in=listCandidateJobId
            ).values_list("id", "closed_at", "ended_at", "run_count"):
                retentionStart = closedAt or endedAt
                if retentionStart is None:
                    continue
                if retentionStart >= historyCutoff and (
                    intRunCount == 0 or intRuns <= limits.maxRunHistoryPerOrganization
                ):
                    continue
                intRuns -= intRunCount
                EmailDelivery.objects.filter(
                    pk__in=listPendingDeliveryId,
                    status=EmailStatus.PENDING,
                    run_reference__run_id__in=Run.objects.filter(job_id=jobId).values(
                        "id"
                    ),
                ).update(
                    status=EmailStatus.NOT_SENT,
                    finished_at=currentTime,
                    reason_code=EmailReasonCode.RUN_NOT_ELIGIBLE,
                )
                Job.objects.filter(pk=jobId).delete()
                intJobsRemoved += 1
            # Keep every no-Run target until the whole remaining request is resolved and old enough.
            protectedJobs = Job.objects.filter(request_id=OuterRef("pk")).filter(
                ~Q(state=JobState.FINISHED)
                | Q(ended_at__isnull=True)
                | Q(ended_at__gt=receiptCutoff)
                | Q(retry_at__isnull=False)
                | Q(attempts__gt=0)
            )
            # Expired permits and Close are not proof that no process was created. The first
            # accepted non-start receipt starts this part of retention; later duplicates do not reset it.
            oldNonStartReceipts = RunEvent.objects.filter(
                assignment_id=OuterRef("pk"),
                kind=RunEventKind.NOT_STARTED,
                received_at__lte=receiptCutoff,
            )
            protectedAssignments = Assignment.objects.filter(
                job__request_id=OuterRef("pk")
            ).filter(
                ~Q(state__in=(AssignmentState.FINISHED, AssignmentState.WITHDRAWN))
                | (Q(permit_expires_at__isnull=False) & ~Exists(oldNonStartReceipts))
            )
            retainedRuns = Run.objects.filter(job__request_id=OuterRef("pk"))
            listExpiredRequestId = list(
                JobRequest.objects
                .filter(
                    ~Exists(protectedJobs),
                    ~Exists(protectedAssignments),
                    ~Exists(retainedRuns),
                    organization_id=organizationId,
                    accepted_at__lte=receiptCutoff,
                )
                .order_by("accepted_at", "id")
                .values_list("id", flat=True)[:limit]
            )
            # Cascading removes the request, all remaining Jobs, assignments and server receipts together.
            _, dictRemoved = JobRequest.objects.filter(
                pk__in=listExpiredRequestId
            ).delete()
            intJobsRemoved += dictRemoved.get(Job._meta.label, 0)
    listTriggerId = list(
        ScheduleTrigger.objects
        .filter(recorded_at__lte=receiptCutoff)
        .exclude(job_request_id__in=JobRequest.objects.values("id"))
        .order_by("recorded_at", "id")
        .values_list("id", flat=True)[:limit]
    )
    ScheduleTrigger.objects.filter(pk__in=listTriggerId).delete()
    RunFileTransfer.objects.filter(expires_at__lte=currentTime).delete()
    return intJobsRemoved, intLogsCleared
