# FileName: retention.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from organizations.models import Organization
from organizations.limits import get_organization_limits, get_run_log_retention_days
from notifications.contracts import EmailStatus, EmailReasonCode
from notifications.models import EmailDelivery
from schedules.models import ScheduleTrigger

from .contracts import JobState, AssignmentState, RunEventKind
from .models import JobRequest, Job, Assignment, Run, RunFileTransfer, RunEvent

from .log_storage import (
    get_or_create_run_log_usage,
    get_clearable_log_runs,
    clear_run_logs,
)

_INT_RECEIPT_RETENTION_DAYS = 30


def cleanup_run_data(limit: int = 200) -> tuple[int, int]:
    """Clear only finished Job groups; keep active and unconfirmed work."""
    intJobsRemoved = 0
    intLogsCleared = 0
    currentTime = timezone.now()
    receiptCutoff = currentTime - timedelta(days=_INT_RECEIPT_RETENTION_DAYS)
    for organization in Organization.objects.only("id", "limit_overrides").iterator(
        chunk_size=100
    ):
        organizationId = organization.pk
        limits = get_organization_limits(organization)
        historyCutoff = currentTime - timedelta(days=limits.runHistoryRetentionDays)
        # Actual history and explicit Close use ordinary retention. No-Run receipts have their own window.
        finishedCandidates = (
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
            finishedCandidates = finishedCandidates.filter(
                retention_start__lt=historyCutoff
            )
        else:
            finishedCandidates = finishedCandidates.filter(
                Q(run_count__gt=0) | Q(retention_start__lt=historyCutoff)
            )
        listCandidateJobId = list(
            finishedCandidates.order_by("retention_start", "id").values_list(
                "id", flat=True
            )[:limit]
        )
        # Finished Jobs cannot create new Run-email events; lock email deliveries before the organization.
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
            organization = Organization.objects.select_for_update().get(pk=organizationId)
            limits = get_organization_limits(organization)
            historyCutoff = currentTime - timedelta(days=limits.runHistoryRetentionDays)
            logCutoff = currentTime - timedelta(
                days=get_run_log_retention_days(organization)
            )
            usage = get_or_create_run_log_usage(organizationId)
            intBytes = usage.used_bytes
            intGroups = usage.group_count
            listExpiredRun: list[Run] = []
            for run in get_clearable_log_runs(organizationId)[:limit]:
                retentionStart = run.job.closed_at or run.job.ended_at
                if retentionStart is None:
                    continue
                boolOld = retentionStart < logCutoff
                if (
                    not boolOld
                    and intBytes <= limits.maxRunLogBytesPerOrganization
                    and intGroups <= limits.maxRunLogGroupsPerOrganization
                ):
                    continue
                listExpiredRun.append(run)
                intBytes -= run.log_bytes
                intGroups -= int(run.log_bytes > 0)
            clear_run_logs(usage, listExpiredRun, currentTime)
            intLogsCleared += len(listExpiredRun)
            # The transfer layer decides when a download reservation can be released.
            # Keep history while any reservation remains, including expired transfers still active in the proxy.
            reservedTransfers = RunFileTransfer.objects.filter(run__job_id=OuterRef("pk"))
            finishedJobs = (
                Job.objects
                .filter(
                    ~Exists(reservedTransfers),
                    request__organization_id=organizationId,
                    state=JobState.FINISHED,
                )
                .annotate(run_count=Count("runs"))
                .filter(Q(run_count__gt=0) | Q(closed_at__isnull=False))
                .order_by("ended_at", "id")
            )
            intRuns = Run.objects.filter(
                job__request__organization_id=organizationId,
                job__state=JobState.FINISHED,
            ).count()
            listRemovedJobId = []
            for jobId, closedAt, endedAt, intRunCount in finishedJobs.filter(
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
                listRemovedJobId.append(jobId)
            if listRemovedJobId:
                EmailDelivery.objects.filter(
                    pk__in=listPendingDeliveryId,
                    status=EmailStatus.PENDING,
                    run_reference__run_id__in=Run.objects.filter(
                        job_id__in=listRemovedJobId
                    ).values("id"),
                ).update(
                    status=EmailStatus.NOT_SENT,
                    finished_at=currentTime,
                    reason_code=EmailReasonCode.RUN_NOT_ELIGIBLE,
                )
                listRemovedRun = list(
                    Run.objects.filter(job_id__in=listRemovedJobId, log_bytes__gt=0).only(
                        "id", "log_bytes"
                    )
                )
                clear_run_logs(usage, listRemovedRun, currentTime)
                Job.objects.filter(pk__in=listRemovedJobId).delete()
                intJobsRemoved += len(listRemovedJobId)
            # Keep every no-Run target until the whole remaining request is resolved and old enough.
            protectedJobs = Job.objects.filter(request_id=OuterRef("pk")).filter(
                ~Q(state=JobState.FINISHED)
                | Q(ended_at__isnull=True)
                | Q(ended_at__gt=receiptCutoff)
                | Q(retry_at__isnull=False)
                | Q(attempt_count__gt=0)
            )
            # Expired permissions and Close do not prove that no process started.
            # Count this retention period from the first accepted Not Started event; repeated events do not reset it.
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
    return intJobsRemoved, intLogsCleared
