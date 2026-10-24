# FileName: usage.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import hashlib
import json
from typing import cast

from django.conf import settings
from django.db.models import Count, Q, Sum
from django.utils import timezone

from assets.models import Asset
from console_project.config import LimitsConfig
from data_queues.models import DataQueue, QueueItem
from executors.models import Executor, ExecutorGroup
from file_storage.models import DownloadSession
from file_storage.proxy import get_download_proxy_snapshot
from file_storage.services import FileOperationError, get_storage_usage
from notifications.contracts import RunEmailRecipientStatus
from notifications.recipients import get_recipient_query
from operations.contracts import (
    OrganizationLimitResponse,
    OrganizationLimitIdentityResponse,
    OrganizationRetentionResponse,
    OrganizationLimitsResponse,
)
from packages.contracts import PackageUploadState
from packages.models import Package, PackageUpload
from runs.contracts import JobState
from runs.models import Job, Run, RunLogUsage, RunFileTransfer
from schedules.models import Schedule
from shared_files.contracts import UploadState
from shared_files.models import SharedFile, UploadSession

from .models import Organization, Membership, Department, MemberInvitation
from .limits import (
    OrganizationLimit,
    LIMIT_DEFINITIONS,
    get_run_log_retention_days,
    get_organization_limits,
)


def get_limits_version(organization: Organization) -> str:
    """Bind an edit to its displayed defaults and explicit overrides, not changing usage."""
    defaults = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    return hashlib.sha256(
        json.dumps(
            {
                "defaults": {
                    definition.configName: getattr(defaults, definition.configName)
                    for definition in LIMIT_DEFINITIONS
                },
                "overrides": organization.limit_overrides,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def get_organization_capacity_usage(
    organization: Organization,
) -> dict[OrganizationLimit, tuple[int, int | None]]:
    """Read capacity balances without counting unrelated objects or contacting the file proxy."""
    storage = get_storage_usage(organization)
    queueUsage = QueueItem.objects.filter(
        queue__department__organization=organization
    ).aggregate(items=Count("pk"), bytes=Sum("size_bytes", default=0))
    logUsage = RunLogUsage.objects.filter(organization=organization).first()
    return {
        OrganizationLimit.STORED_BYTES: (
            storage["used_bytes"],
            storage["reserved_bytes"],
        ),
        OrganizationLimit.QUEUE_ITEMS: (queueUsage["items"], None),
        OrganizationLimit.QUEUE_DATA_BYTES: (queueUsage["bytes"], None),
        OrganizationLimit.RUN_LOG_BYTES: (logUsage.used_bytes if logUsage else 0, None),
        OrganizationLimit.RUN_LOG_GROUPS: (logUsage.group_count if logUsage else 0, None),
        OrganizationLimit.RUN_HISTORY: (
            Run.objects.filter(
                job__request__organization=organization, job__state=JobState.FINISHED
            ).count(),
            None,
        ),
    }


def get_organization_usage(organization: Organization) -> OrganizationLimitsResponse:
    """Read current counters on demand without creating history or changing reservations."""
    currentTime = timezone.now()
    defaults = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    limits = get_organization_limits(organization)
    projects = (
        Package.objects
        .filter(department__organization=organization)
        .values("department_id", "project_name_key")
        .annotate(packages=Count("pk"))
    )
    # Only the highest current project usage can be compared with a per-project limit.
    intMostPackages = (
        projects.order_by("-packages").values_list("packages", flat=True).first() or 0
    )
    intPendingMembers = MemberInvitation.objects.filter(
        organization=organization,
        accepted_at__isnull=True,
        revoked_at__isnull=True,
        expires_at__gt=currentTime,
    ).count()
    intUploads = (
        PackageUpload.objects.filter(
            organization=organization,
            state=PackageUploadState.RECEIVING,
            expires_at__gt=currentTime,
        ).count()
        + UploadSession.objects.filter(
            organization=organization,
            state=UploadState.RECEIVING,
            expires_at__gt=currentTime,
        ).count()
    )
    intDownloads: int | None = None
    strUsageWarning: str | None = None
    try:
        # A proxy may still be sending after the source lease expires.
        proxySnapshot = get_download_proxy_snapshot()
    except FileOperationError:
        strUsageWarning = "Download activity is temporarily unavailable."
    else:
        downloadCondition = Q(expires_at__gt=currentTime)
        if proxySnapshot is not None:
            downloadCondition = Q(expires_at__gt=proxySnapshot.capturedAt) | Q(
                pk__in=proxySnapshot.activeIds
            )
        intDownloads = (
            DownloadSession.objects.filter(
                downloadCondition, organization=organization
            ).count()
            + RunFileTransfer.objects.filter(
                downloadCondition, organization=organization
            ).count()
        )

    dictUsage: dict[OrganizationLimit, tuple[int | None, int | None]] = {
        **get_organization_capacity_usage(organization),
        OrganizationLimit.MEMBERS: (
            Membership.objects.filter(organization=organization).count(),
            intPendingMembers,
        ),
        OrganizationLimit.DEPARTMENTS: (
            Department.objects.filter(
                organization=organization, deleted_at__isnull=True
            ).count(),
            None,
        ),
        OrganizationLimit.EXECUTORS: (
            Executor.objects.filter(
                department__organization=organization, deleted_at__isnull=True
            ).count(),
            None,
        ),
        OrganizationLimit.EXECUTOR_GROUPS: (
            ExecutorGroup.objects.filter(department__organization=organization).count(),
            None,
        ),
        OrganizationLimit.PROJECTS: (projects.count(), None),
        OrganizationLimit.PACKAGES_PER_PROJECT: (intMostPackages, None),
        OrganizationLimit.SCHEDULES: (
            Schedule.objects.filter(department__organization=organization).count(),
            None,
        ),
        OrganizationLimit.ASSETS: (
            Asset.objects.filter(department__organization=organization).count(),
            None,
        ),
        OrganizationLimit.DATA_QUEUES: (
            DataQueue.objects.filter(department__organization=organization).count(),
            None,
        ),
        OrganizationLimit.SHARED_FILES: (
            SharedFile.objects.filter(department__organization=organization).count(),
            None,
        ),
        OrganizationLimit.RUN_EMAIL_ADDRESSES: (
            get_recipient_query(organization.pk)
            .exclude(status=RunEmailRecipientStatus.MEMBER)
            .count(),
            None,
        ),
        OrganizationLimit.ACTIVE_JOBS: (
            Job.objects
            .filter(request__organization=organization)
            .exclude(state=JobState.FINISHED)
            .count(),
            None,
        ),
        OrganizationLimit.ACTIVE_UPLOADS: (intUploads, None),
        OrganizationLimit.ACTIVE_DOWNLOADS: (intDownloads, None),
    }
    # Rate and burst limits are not resource balances; leave Used and Reserved unset.
    return OrganizationLimitsResponse(
        organization=OrganizationLimitIdentityResponse(
            id=organization.pk, name=organization.name
        ),
        limits=[
            OrganizationLimitResponse(
                key=definition.key,
                label=definition.label,
                unit=definition.unit,
                used=dictUsage.get(definition.key, (None, None))[0],
                reserved=dictUsage.get(definition.key, (None, None))[1],
                limit=getattr(limits, definition.configName),
                default_limit=getattr(defaults, definition.configName),
                override=organization.limit_overrides.get(definition.configName),
                minimum=definition.minimum,
                maximum=definition.maximum,
            )
            for definition in LIMIT_DEFINITIONS
        ],
        version=get_limits_version(organization),
        updated_at=currentTime,
        usage_warning=strUsageWarning,
        retention=OrganizationRetentionResponse(
            run_log_days=get_run_log_retention_days(organization),
            run_log_max_days=defaults.runLogRetentionDays,
            run_history_days=limits.runHistoryRetentionDays,
            audit_days=limits.auditRetentionDays,
        ),
    )
