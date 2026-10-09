# FileName: models.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.db import models
from django.utils import timezone

from console_project.constants import (
    INT_DISPLAY_NAME_SNAPSHOT_MAX_LENGTH,
    INT_WINDOWS_NAME_MAX_LENGTH,
    RunLogLevel,
)

from .contracts import (
    INT_DESCRIPTION_MAX_LENGTH,
    INT_VERSION_SUMMARY_MAX_LENGTH,
    INT_MAX_RETRY_COUNT,
    INT_MAX_TIMEOUT_MIN,
    RunConflictPolicy,
    RunPriority,
    build_default_run_email,
    PackagePreparationState,
)


class Package(models.Model):
    department_id: uuid.UUID
    blob_id: uuid.UUID

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    department = models.ForeignKey("organizations.Department", on_delete=models.PROTECT)
    project_name = models.CharField(max_length=255)
    project_name_key = models.CharField(max_length=255, db_collation="C")
    version = models.CharField(max_length=INT_WINDOWS_NAME_MAX_LENGTH)
    version_key = models.CharField(
        max_length=INT_WINDOWS_NAME_MAX_LENGTH, db_collation="C"
    )
    description = models.CharField(max_length=INT_DESCRIPTION_MAX_LENGTH)
    version_summary = models.CharField(max_length=INT_VERSION_SUMMARY_MAX_LENGTH)
    requires_liberrpa = models.TextField()
    component_dependencies = models.JSONField(default=dict)
    argument_names = models.JSONField(default=list)
    blob = models.OneToOneField("file_storage.StoredBlob", on_delete=models.PROTECT)
    python_environment_name = models.CharField(
        max_length=INT_WINDOWS_NAME_MAX_LENGTH, default="default"
    )
    retry_count = models.PositiveSmallIntegerField(default=0)
    timeout_min = models.PositiveIntegerField(default=0)
    builtin_log_level = models.CharField(
        max_length=max(len(entry.value) for entry in RunLogLevel),
        choices=[(entry.value, entry.value) for entry in RunLogLevel],
        default=RunLogLevel.INFO,
    )
    builtin_record_video = models.BooleanField(default=False)
    builtin_stop_shortcut = models.BooleanField(default=True)
    builtin_highlight_ui = models.BooleanField(default=False)
    custom_prj_args = models.JSONField(default=list, blank=True)
    custom_arg_assets = models.JSONField(default=list, blank=True)
    run_conflict_policy = models.CharField(
        max_length=max(len(entry.value) for entry in RunConflictPolicy),
        choices=[(entry.value, entry.value) for entry in RunConflictPolicy],
        default=RunConflictPolicy.WAIT,
    )
    priority = models.CharField(
        max_length=max(len(entry.value) for entry in RunPriority),
        choices=[(entry.value, entry.value) for entry in RunPriority],
        default=RunPriority.NORMAL,
    )
    api_input_keys = models.JSONField(default=list, blank=True)
    run_email = models.JSONField(default=build_default_run_email)
    uploaded_by_id = models.UUIDField()
    uploaded_by_name = models.CharField(max_length=INT_DISPLAY_NAME_SNAPSHOT_MAX_LENGTH)
    uploaded_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    @property
    def sha256(self) -> str:
        return self.blob.sha256

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["department", "project_name_key", "version_key"],
                name="package_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    run_conflict_policy__in=[entry.value for entry in RunConflictPolicy]
                ),
                name="package_conflict_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(priority__in=[entry.value for entry in RunPriority]),
                name="package_priority_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    retry_count__gte=0, retry_count__lte=INT_MAX_RETRY_COUNT
                ),
                name="package_retry_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    timeout_min__gte=0, timeout_min__lte=INT_MAX_TIMEOUT_MIN
                ),
                name="package_timeout_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    builtin_log_level__in=[entry.value for entry in RunLogLevel]
                ),
                name="package_log_level_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.project_name} {self.version}"


class PackageUploadState(models.TextChoices):
    RECEIVING = "receiving", "Receiving"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    EXPIRED = "expired", "Expired"
    CANCELED = "canceled", "Canceled"


class PackageUpload(models.Model):
    organization_id: uuid.UUID
    blob_id: uuid.UUID | None

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE
    )
    actor_id = models.UUIDField()
    department_id = models.UUIDField()
    request_id = models.UUIDField()
    size_bytes = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64)
    blob = models.OneToOneField(
        "file_storage.StoredBlob", null=True, on_delete=models.SET_NULL
    )
    state = models.CharField(
        max_length=max(len(value) for value in PackageUploadState.values),
        choices=PackageUploadState.choices,
        default=PackageUploadState.RECEIVING,
    )
    offset = models.PositiveBigIntegerField(default=0)
    result = models.JSONField(null=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "actor_id", "request_id"],
                name="package_upload_request_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(state__in=PackageUploadState.values),
                name="package_upload_state_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(offset__lte=models.F("size_bytes")),
                name="package_upload_offset_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organization", "state", "expires_at"],
                name="package_upload_expiry",
            )
        ]


class PackageUploadChunk(models.Model):
    upload = models.ForeignKey(PackageUpload, on_delete=models.CASCADE)
    offset = models.PositiveBigIntegerField()
    size_bytes = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["upload", "offset"], name="package_chunk_offset_unique"
            )
        ]


class PackagePreparation(models.Model):
    package_id: uuid.UUID
    executor_id: uuid.UUID

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    package = models.ForeignKey(Package, on_delete=models.CASCADE)
    executor = models.ForeignKey("executors.Executor", on_delete=models.CASCADE)
    session_id = models.UUIDField(null=True)
    python_environment_name = models.CharField(max_length=INT_WINDOWS_NAME_MAX_LENGTH)
    state = models.CharField(
        max_length=max(len(value) for value in PackagePreparationState.values),
        choices=PackagePreparationState.choices,
        default=PackagePreparationState.PENDING,
    )
    reason = models.CharField(max_length=2000, blank=True)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["package", "executor", "python_environment_name"],
                name="package_preparation_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(state__in=PackagePreparationState.values),
                name="package_preparation_state_valid",
            ),
        ]
