# FileName: run_events.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from typing import TYPE_CHECKING

from runs.contracts import JobSource

from .models import (
    EmailType,
    EmailDelivery,
    RunEmailEvent,
    RunEmailReference,
)
from .recipients import get_eligible_recipients
from .run_email import DICT_RUN_EMAIL_EVENT_KEY
from .services import notify_prestart_failure, notify_needs_review

if TYPE_CHECKING:
    from runs.models import Job, Assignment, Run


def notify_run_event(run: "Run", event: RunEmailEvent) -> None:
    if run.job.closed_at is not None:
        return
    strKey = DICT_RUN_EMAIL_EVENT_KEY[event]
    dictConfig = run.job.run_snapshot.get("run_email", {})
    if not dictConfig.get(strKey, {}).get("enabled", False):
        return
    organizationId = run.job.request.organization_id
    strOrganizationName = run.job.request.organization.name
    for recipient in get_eligible_recipients(organizationId).filter(
        pk__in=dictConfig.get("recipient_ids", [])
    ):
        if RunEmailReference.objects.filter(
            run_id=run.pk, event=event, recipient=recipient
        ).exists():
            continue
        delivery = EmailDelivery.objects.create(
            organization_id=organizationId,
            organization_name=strOrganizationName,
            email_type=EmailType.RUN,
            recipient=recipient.email,
        )
        RunEmailReference.objects.create(
            delivery=delivery,
            organization_id=organizationId,
            recipient=recipient,
            run_id=run.pk,
            event=event,
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


def notify_job_needs_review(job: "Job", assignment: "Assignment") -> None:
    notify_needs_review(
        organizationId=job.request.organization_id,
        departmentId=job.department_id,
        creatorId=job.request.actor_id,
        title="Job needs review",
        detail=(
            f"Project: {job.project_name}\nVersion: {job.project_version}\n"
            f"Executor: {assignment.executor_name}\nJob ID: {job.pk}\n"
            f"Reason: {job.reason}\n\n"
            "Review the Job and check the Executor. If no further Console management "
            "is needed, use Close Job."
        ),
        eventKey=f"assignment:{assignment.pk}:needs_review",
    )
