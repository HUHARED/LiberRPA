# FileName: email_retention.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import timedelta
from typing import cast

from django.conf import settings
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from console_project.config import LimitsConfig

from .models import EmailStatus, EmailDelivery
from .delivery import EMAIL_BUDGET_WINDOW


def _delete_in_batches(records: QuerySet[EmailDelivery], batchSize: int) -> int:
    intDeletedCount = 0
    while True:
        with transaction.atomic():
            listDeliveryId = list(
                records
                .select_for_update(skip_locked=True, of=("self",))
                .order_by("finished_at", "id")
                .values_list("id", flat=True)[:batchSize]
            )
            if not listDeliveryId:
                return intDeletedCount
            _, dictDeletedCount = records.filter(pk__in=listDeliveryId).delete()
            intDeletedCount += dictDeletedCount.get(EmailDelivery._meta.label, 0)


def prune_email_deliveries(*, batchSize: int = 1000) -> int:
    """Prune completed history by organization while preserving live accounting and proofs."""
    if not 1 <= batchSize <= 10000:
        raise ValueError("Batch size must be between 1 and 10000.")
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    currentTime = timezone.now()
    instanceDayStart = timezone.localtime(
        currentTime, timezone.get_default_timezone()
    ).replace(hour=0, minute=0, second=0, microsecond=0)
    # Keep budget usage, resend cursors, valid email proofs, and the instance's Failed Today count.
    protectedCutoff = min(
        currentTime
        - max(EMAIL_BUDGET_WINDOW, timedelta(seconds=limits.emailResendSeconds)),
        instanceDayStart,
    )
    retentionCutoff = currentTime - timedelta(days=limits.emailDeliveryRetentionDays)
    completed = EmailDelivery.objects.filter(
        status__in=[
            EmailStatus.ACCEPTED,
            EmailStatus.FAILED,
            EmailStatus.NOT_SENT,
            EmailStatus.UNKNOWN,
        ],
        finished_at__isnull=False,
    )
    intDeletedCount = 0
    # Historical organization IDs remain separate even after the organization is deleted.
    for organizationId in (
        completed
        .order_by("organization_id")
        .values_list("organization_id", flat=True)
        .distinct()
        .iterator(chunk_size=100)
    ):
        records = completed.filter(organization_id=organizationId)
        eligible = records.filter(finished_at__lt=protectedCutoff)
        intDeletedCount += _delete_in_batches(
            eligible.filter(finished_at__lt=retentionCutoff), batchSize
        )
        intLimit = (
            limits.maxEmailDeliveriesWithoutOrganization
            if organizationId is None
            else limits.maxEmailDeliveriesPerOrganization
        )
        # Freeze the excess boundary so concurrent cleanup never reaches newer retained history.
        dictCutoff = (
            records
            .order_by("-finished_at", "-id")
            .values("finished_at", "id")[intLimit : intLimit + 1]
            .first()
        )
        if dictCutoff is not None:
            intDeletedCount += _delete_in_batches(
                eligible.filter(
                    Q(finished_at__lt=dictCutoff["finished_at"])
                    | Q(finished_at=dictCutoff["finished_at"], id__lte=dictCutoff["id"])
                ),
                batchSize,
            )
    return intDeletedCount
