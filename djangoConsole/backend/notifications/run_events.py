# FileName: run_events.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from runs.models import Job, Run

from runs.models import JobSource

from .models import (
    EmailType,
    EmailDelivery,
    RunEmailRecipient,
    RunEmailEvent,
    RunEmailReference,
)
from .services import notify_prestart_failure


def notify_run_event(run: "Run", event: str) -> None:
    if run.job.closed_at is not None:
        return
    emailEvent = RunEmailEvent(event)
    strKey = {
        RunEmailEvent.START: "on_start",
        RunEmailEvent.COMPLETED: "on_completed",
        RunEmailEvent.ERROR: "on_error",
    }[emailEvent]
    dictConfig = run.job.run_snapshot.get("run_email", {})
    if not dictConfig.get(strKey, {}).get("enabled", False):
        return
    organizationId = run.job.request.organization_id
    for recipient in RunEmailRecipient.objects.filter(
        pk__in=dictConfig.get("recipient_ids", []),
        organization_id=organizationId,
        verified_at__isnull=False,
    ):
        if RunEmailReference.objects.filter(
            run_id=run.pk, event=emailEvent, recipient=recipient
        ).exists():
            continue
        delivery = EmailDelivery.objects.create(
            email_type=EmailType.RUN, recipient=recipient.email
        )
        RunEmailReference.objects.create(
            delivery=delivery,
            organization_id=organizationId,
            recipient=recipient,
            run_id=run.pk,
            event=emailEvent,
        )


def notify_job_failure(job: "Job") -> None:
    jobRequest = job.request
    creatorId = jobRequest.actor_id
    notify_prestart_failure(
        organizationId=jobRequest.organization_id,
        departmentId=job.department_id,
        creatorId=creatorId,
        source=JobSource(jobRequest.source),
        title="Job could not start",
        detail=f"Project: {job.project_name}\nVersion: {job.project_version}\nTarget: {job.target_name}\nReason: {job.reason}",
        eventKey=f"job:{job.pk}:prestart_failure",
    )
