# FileName: retention.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Sum, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from organizations.models import Organization
from notifications.models import EmailDelivery, EmailStatus, EmailReasonCode
from schedules.models import ScheduleTrigger

from .models import Job, JobRequest, JobState, Run, RunFileTransfer, RunLog


def prune_run_data(limit: int = 200) -> tuple[int, int]:
    """Clear only terminal Job groups; active and unresolved work stays protected."""
    intJobsRemoved = 0
    intLogsCleared = 0
    currentTime = timezone.now()
    limits = settings.CONSOLE_LIMITS
    for organizationId in Organization.objects.values_list("id", flat=True).iterator(
        chunk_size=100
    ):
        # Select eligible ages before limiting, so young Run history cannot hide expired no-Run receipts.
        terminalCandidates = Job.objects.filter(
            request__organization_id=organizationId, state=JobState.FINISHED
        ).annotate(
            run_count=Count("runs"), retention_start=Coalesce("closed_at", "ended_at")
        )
        intExistingRuns = Run.objects.filter(
            job__request__organization_id=organizationId,
            job__state=JobState.FINISHED,
        ).count()
        if intExistingRuns <= limits.maxRunHistoryPerOrganization:
            terminalCandidates = terminalCandidates.filter(
                Q(
                    run_count__gt=0,
                    retention_start__lt=currentTime
                    - timedelta(days=limits.runHistoryRetentionDays),
                )
                | Q(run_count=0, retention_start__lt=currentTime - timedelta(days=30))
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
                intDays = limits.runHistoryRetentionDays if intRunCount else 30
                if (
                    retentionStart >= currentTime - timedelta(days=intDays)
                    and intRuns <= limits.maxRunHistoryPerOrganization
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
            # Receipts do not recreate cleared history; expire them separately after the ordinary retry horizon.
            JobRequest.objects.filter(
                organization_id=organizationId,
                accepted_at__lt=currentTime - timedelta(days=30),
                jobs__isnull=True,
            ).delete()
    listTriggerId = list(
        ScheduleTrigger.objects
        .filter(recorded_at__lt=currentTime - timedelta(days=30))
        .order_by("recorded_at", "id")
        .values_list("id", flat=True)[:limit]
    )
    ScheduleTrigger.objects.filter(pk__in=listTriggerId).delete()
    RunFileTransfer.objects.filter(expires_at__lte=currentTime).delete()
    return intJobsRemoved, intLogsCleared
