# FileName: browser_events.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from collections.abc import Iterable

from django.db.models import Exists, OuterRef, Q
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from accounts.contracts import BrowserMessageType
from console_project.db_notifications import (
    NotificationChannel,
    publish_database_notification,
)
from executors.models import Executor, ExecutorGroup
from notifications.models import RunEmailRecipient
from organizations.contracts import DepartmentRole
from organizations.models import Membership
from organizations.permissions import get_department_access_query
from schedules.models import Schedule

from .models import Job, Assignment, Run, RunEvent

_SET_RUN_LOG_FIELD = frozenset({
    "log_bytes",
    "logs_complete",
    "logs_unavailable_reason",
})


def _notify_job_changed(job: Job) -> None:
    """Notify current readers without publishing execution data or extending their access."""
    organizationId = job.request.organization_id
    departmentQuery = get_department_access_query(
        actorId=OuterRef("user_id"),
        organizationId=organizationId,
        isOrgAdmin=False,
        requiredRole=DepartmentRole.OPERATOR,
    ).filter(pk=job.department_id)
    # Administrators can still read history belonging to a deleted department.
    userQuery = Membership.objects.filter(
        Q(is_org_admin=True) | Exists(departmentQuery),
        organization_id=organizationId,
        user__is_active=True,
        user__is_platform_admin=False,
    ).values_list("user_id", flat=True)
    for userId in userQuery:
        publish_database_notification(
            NotificationChannel.BROWSER_EVENTS,
            f"{BrowserMessageType.EXECUTION_CHANGED}:{userId}:{job.pk}",
        )


def notify_jobs_changed(jobIds: Iterable[uuid.UUID]) -> None:
    """Cover bulk updates in the caller's transaction; PostgreSQL coalesces identical hints."""
    for job in (
        Job.objects
        .filter(pk__in=set(jobIds))
        .select_related("request")
        .only("id", "department_id", "request__organization_id")
    ):
        _notify_job_changed(job)


@receiver(post_save, sender=Job)
def _job_saved(*, instance: Job, raw: bool, **_kwargs: object) -> None:
    if not raw:
        _notify_job_changed(instance)


@receiver(pre_delete, sender=Job)
def _job_deleting(*, instance: Job, **_kwargs: object) -> None:
    # Resolve the request before a cascading deletion removes its authorization scope.
    _notify_job_changed(instance)


@receiver(post_save, sender=Assignment)
def _assignment_saved(
    *,
    instance: Assignment,
    raw: bool,
    update_fields: frozenset[str] | None,
    **_kwargs: object,
) -> None:
    if not raw and (update_fields is None or update_fields.difference({"received_at"})):
        _notify_job_changed(instance.job)


@receiver(post_save, sender=Run)
def _run_saved(
    *,
    instance: Run,
    raw: bool,
    update_fields: frozenset[str] | None,
    **_kwargs: object,
) -> None:
    # Run Logs owns its refresh switch; uploaded log batches do not refresh the details page.
    if not raw and (
        update_fields is None or update_fields.difference(_SET_RUN_LOG_FIELD)
    ):
        _notify_job_changed(instance.job)


@receiver(post_save, sender=RunEvent)
def _run_event_saved(*, instance: RunEvent, raw: bool, **_kwargs: object) -> None:
    if not raw:
        _notify_job_changed(instance.assignment.job)


@receiver(pre_delete, sender=Schedule)
def _schedule_deleting(*, instance: Schedule, **_kwargs: object) -> None:
    notify_jobs_changed(
        Job.objects.filter(request__schedule_id=instance.pk).values_list("id", flat=True)
    )


@receiver(pre_delete, sender=ExecutorGroup)
def _executor_group_deleting(*, instance: ExecutorGroup, **_kwargs: object) -> None:
    notify_jobs_changed(
        Job.objects.filter(target_group_id=instance.pk).values_list("id", flat=True)
    )


@receiver(post_save, sender=Executor)
def _executor_saved(
    *,
    instance: Executor,
    raw: bool,
    update_fields: frozenset[str] | None,
    **_kwargs: object,
) -> None:
    if (
        raw
        or instance.deleted_at is None
        or (update_fields is not None and "deleted_at" not in update_fields)
    ):
        return
    notify_jobs_changed(
        Job.objects.filter(
            Q(target_executor_id=instance.pk) | Q(assignments__executor_id=instance.pk)
        ).values_list("id", flat=True)
    )


@receiver(pre_delete, sender=RunEmailRecipient)
def _run_email_recipient_deleting(
    *, instance: RunEmailRecipient, **_kwargs: object
) -> None:
    notify_jobs_changed(
        Job.objects.filter(
            request__organization_id=instance.organization_id,
            run_snapshot__run_email__recipient_ids__contains=[str(instance.pk)],
        ).values_list("id", flat=True)
    )
