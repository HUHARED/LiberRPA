# FileName: cleanup.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from file_storage.models import StoredBlobPurpose, StoredBlobState, StoredBlob
from organizations.models import Organization

from .models import Package, PackageUpload, PackageUploadState


def expire_uploads(organizationId: uuid.UUID) -> None:
    uploads = PackageUpload.objects.filter(
        organization_id=organizationId,
        state=PackageUploadState.RECEIVING,
        expires_at__lte=timezone.now(),
    )
    StoredBlob.objects.filter(pk__in=uploads.values("blob_id")).update(
        state=StoredBlobState.GARBAGE
    )
    uploads.update(state=PackageUploadState.EXPIRED)
    PackageUpload.objects.filter(
        organization_id=organizationId,
        created_at__lt=timezone.now()
        - timedelta(days=settings.CONSOLE_LIMITS.fileReceiptRetentionDays),
    ).exclude(state=PackageUploadState.RECEIVING).delete()


def cleanup_uploads(limit: int = 200) -> None:
    currentTime = timezone.now()
    cutoff = currentTime - timedelta(
        days=settings.CONSOLE_LIMITS.fileReceiptRetentionDays
    )
    listOrganizationId = list(
        PackageUpload.objects
        .filter(
            Q(state=PackageUploadState.RECEIVING, expires_at__lte=currentTime)
            | Q(created_at__lt=cutoff)
        )
        .order_by("expires_at")
        .values_list("organization_id", flat=True)[:limit]
    )
    for organizationId in set(listOrganizationId):
        with transaction.atomic():
            if (
                Organization.objects
                .select_for_update()
                .filter(pk=organizationId)
                .exists()
            ):
                expire_uploads(organizationId)


@transaction.atomic
def prepare_organization_package_cleanup(organizationId: uuid.UUID) -> None:
    organization = Organization.objects.select_for_update().get(pk=organizationId)
    if organization.deletion_started_at is None:
        raise RuntimeError("Organization deletion has not started.")
    Package.objects.filter(department__organization_id=organizationId).delete()
    PackageUpload.objects.filter(
        organization_id=organizationId, state=PackageUploadState.RECEIVING
    ).update(state=PackageUploadState.CANCELED)
    StoredBlob.objects.filter(
        organization_id=organizationId, purpose=StoredBlobPurpose.PACKAGE
    ).update(state=StoredBlobState.GARBAGE)
