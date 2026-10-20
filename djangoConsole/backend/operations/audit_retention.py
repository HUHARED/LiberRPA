# FileName: audit_retention.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import timedelta
from typing import cast

from django.conf import settings
from django.db.models import Q, QuerySet
from django.utils import timezone

from console_project.config import LimitsConfig

from .models import AuditScope, AuditRecord


def _delete_in_batches(records: QuerySet[AuditRecord], batchSize: int) -> int:
    intDeletedCount = 0
    while True:
        listRecordId = list(
            records.order_by("created_at", "id").values_list("id", flat=True)[:batchSize]
        )
        if not listRecordId:
            return intDeletedCount
        intBatchCount, _ = AuditRecord.objects.filter(pk__in=listRecordId).delete()
        intDeletedCount += intBatchCount


def _prune_scope(records: QuerySet[AuditRecord], limit: int, batchSize: int) -> int:
    # Freeze a cutoff without loading all retained IDs or deleting newly arrived records.
    dictCutoff = (
        records
        .order_by("-created_at", "-id")
        .values("created_at", "id")[limit : limit + 1]
        .first()
    )
    if dictCutoff is None:
        return 0
    return _delete_in_batches(
        records.filter(
            Q(created_at__lt=dictCutoff["created_at"])
            | Q(created_at=dictCutoff["created_at"], id__lte=dictCutoff["id"])
        ),
        batchSize,
    )


def prune_audit_records(*, batchSize: int = 1000) -> int:
    """Apply age and independent per-organization/platform count limits in small batches."""
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    intDeletedCount = _delete_in_batches(
        AuditRecord.objects.filter(
            created_at__lt=timezone.now() - timedelta(days=limits.auditRetentionDays)
        ),
        batchSize,
    )
    for organizationId in (
        AuditRecord.objects
        .filter(scope=AuditScope.ORGANIZATION)
        .order_by("organization_id")
        .values_list("organization_id", flat=True)
        .distinct()
        .iterator()
    ):
        intDeletedCount += _prune_scope(
            AuditRecord.objects.filter(
                scope=AuditScope.ORGANIZATION, organization_id=organizationId
            ),
            limits.maxAuditRecordsPerOrganization,
            batchSize,
        )
    intDeletedCount += _prune_scope(
        AuditRecord.objects.filter(scope=AuditScope.PLATFORM),
        limits.maxPlatformAuditRecords,
        batchSize,
    )
    return intDeletedCount
