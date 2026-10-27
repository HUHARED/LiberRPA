# FileName: browser_events.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from collections.abc import Iterable

from django.db.models import Exists, OuterRef, Q

from accounts.contracts import BrowserMessageType
from console_project.db_notifications import (
    NotificationChannel,
    publish_database_notification,
)
from organizations.contracts import DepartmentRole
from organizations.models import Membership
from organizations.permissions import get_department_access_query

from .models import Job

# Business operations publish after their writes; model signals would repeat reader queries for each saved record.


def notify_job_changed(job: Job) -> None:
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
    """Publish each affected Job once within the caller's transaction."""
    for job in (
        Job.objects
        .filter(pk__in=set(jobIds))
        .select_related("request")
        .only("id", "department_id", "request__organization_id")
    ):
        notify_job_changed(job)
