# FileName: models.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Organization(models.Model):
    """Organization identity; names may repeat across organizations."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    def __str__(self) -> str:
        return self.name


class Membership(models.Model):
    """The account's current organization and organization-level administrator role."""

    # The account ID also identifies its single current membership.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="membership",
    )
    # Organization deletion must first handle its accounts through the cleanup flow.
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    is_org_admin = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default="")
    joined_at = models.DateTimeField(default=timezone.now, editable=False)

    def __str__(self) -> str:
        return f"User {self.user_id} in organization {self.organization_id}"
