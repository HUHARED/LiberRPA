# FileName: models.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.core.validators import MaxLengthValidator, ProhibitNullCharactersValidator
from django.db import models
from django.utils import timezone

from organizations.validators import validate_path_segment

from .contracts import AssetType, SECRET_ASSET_TYPES


class Asset(models.Model):
    department_id: uuid.UUID

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    department = models.ForeignKey(
        "organizations.Department", on_delete=models.PROTECT, related_name="assets"
    )
    name = models.CharField(max_length=128, validators=[validate_path_segment])
    # NOTE: Name writes must update this key through the business service.
    name_key = models.TextField(editable=False, db_collation="C")
    asset_type = models.CharField(
        max_length=max(len(value) for value in AssetType.values),
        choices=AssetType.choices,
        editable=False,
    )
    notes = models.TextField(
        blank=True,
        default="",
        validators=[MaxLengthValidator(2000), ProhibitNullCharactersValidator()],
    )
    # Secret assets leave this field empty; their values are stored in encrypted_value.
    value_json = models.TextField(blank=True, default="", editable=False)
    encrypted_value = models.TextField(blank=True, default="", editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["department", "name_key"],
                name="asset_department_name_unique",
                violation_error_code="duplicate_asset_name",
                violation_error_message="An asset with this name already exists in this department.",
            ),
            models.CheckConstraint(
                condition=models.Q(asset_type__in=AssetType.values),
                name="asset_type_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(asset_type__in=SECRET_ASSET_TYPES, value_json="")
                    & ~models.Q(encrypted_value="")
                )
                | (
                    ~models.Q(asset_type__in=SECRET_ASSET_TYPES)
                    & models.Q(encrypted_value="")
                    & ~models.Q(value_json="")
                ),
                name="asset_value_storage_valid",
            ),
        ]

    def __str__(self) -> str:
        return self.name
