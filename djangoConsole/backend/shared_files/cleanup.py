# FileName: cleanup.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.db import transaction
from django.utils import timezone

from file_storage.models import StoredBlob
from organizations.models import Organization

from .models import SharedFile, UploadSession


def expire_uploads(organizationId: uuid.UUID) -> None:
    """Retire expired uploads under the organization lock; physical cleanup runs separately."""
    uploads = UploadSession.objects.filter(
        organization_id=organizationId, state="receiving", expires_at__lte=timezone.now()
    )
    StoredBlob.objects.filter(pk__in=uploads.values("blob_id")).update(
        state=StoredBlob.State.GARBAGE
    )
    uploads.update(state="expired")


def cleanup_uploads(limit: int = 200) -> None:
    organizationIds = set(
        UploadSession.objects
        .filter(state="receiving", expires_at__lte=timezone.now())
        .order_by("expires_at")
        .values_list("organization_id", flat=True)[:limit]
    )
    for organizationId in organizationIds:
        with transaction.atomic():
            if (
                Organization.objects
                .select_for_update()
                .filter(pk=organizationId)
                .exists()
            ):
                expire_uploads(organizationId)


@transaction.atomic
def prepare_organization_file_cleanup(organizationId: uuid.UUID) -> None:
    organization = Organization.objects.select_for_update().get(pk=organizationId)
    if organization.deletion_started_at is None:
        raise RuntimeError("Organization deletion has not started.")
    SharedFile.objects.filter(department__organization_id=organizationId).delete()
    UploadSession.objects.filter(
        organization_id=organizationId, state="receiving"
    ).update(state="canceled")
    StoredBlob.objects.filter(
        organization_id=organizationId, purpose="shared_file"
    ).update(state=StoredBlob.State.GARBAGE)
