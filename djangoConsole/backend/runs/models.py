# FileName: models.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from typing import TYPE_CHECKING

from django.db import models
from django.db.models.lookups import Exact
from django.utils import timezone

from console_project.constants import (
    INT_DISPLAY_NAME_SNAPSHOT_MAX_LENGTH,
    INT_WINDOWS_NAME_MAX_LENGTH,
    RunLogLevel,
)

from .contracts import (
    JobSource,
    JobState,
    AssignmentState,
    RunResult,
    OutputsStatus,
    RecordingStatus,
    RunEventKind,
    RunFileKind,
)


if TYPE_CHECKING:
    from django.db.models.fields.related_descriptors import RelatedManager


class JobRequest(models.Model):
    jobs: "RelatedManager[Job]"
    organization_id: uuid.UUID
    department_id: uuid.UUID

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE
    )
    department = models.ForeignKey("organizations.Department", on_delete=models.PROTECT)
    client_request_id = models.UUIDField()
    actor_id = models.UUIDField(null=True)
    actor_name = models.CharField(
        max_length=INT_DISPLAY_NAME_SNAPSHOT_MAX_LENGTH, blank=True
    )
    source = models.CharField(
        max_length=max(len(value) for value in JobSource.values),
        choices=JobSource.choices,
    )
    request_digest = models.CharField(max_length=64)
    schedule_id = models.UUIDField(null=True)
    schedule_name = models.CharField(max_length=128, blank=True)
    scheduled_at = models.DateTimeField(null=True)
    accepted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "actor_id", "source", "client_request_id"],
                name="job_request_identity_unique",
                nulls_distinct=False,
            ),
            models.UniqueConstraint(
                fields=["schedule_id", "scheduled_at"],
                condition=models.Q(source=JobSource.SCHEDULE),
                name="job_schedule_trigger_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(source__in=JobSource.values),
                name="job_request_source_valid",
            ),
        ]


class Job(models.Model):
    assignments: "RelatedManager[Assignment]"
    runs: "RelatedManager[Run]"
    request_id: uuid.UUID
    department_id: uuid.UUID

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(JobRequest, on_delete=models.CASCADE, related_name="jobs")
    department = models.ForeignKey("organizations.Department", on_delete=models.PROTECT)
    package_id = models.UUIDField()
    project_name = models.CharField(max_length=255)
    project_version = models.CharField(max_length=INT_WINDOWS_NAME_MAX_LENGTH)
    target_executor_id = models.UUIDField(null=True)
    target_group_id = models.UUIDField(null=True)
    target_name = models.CharField(max_length=128)
    # Direct work stays bound to its accepted association, including retries.
    target_session_id = models.UUIDField(null=True)
    run_snapshot = models.JSONField()
    state = models.CharField(
        max_length=max(len(value) for value in JobState.values),
        choices=JobState.choices,
        default=JobState.WAITING,
    )
    priority_rank = models.PositiveSmallIntegerField(default=1)
    reason = models.CharField(max_length=2000, blank=True)
    queued_at = models.DateTimeField(default=timezone.now)
    attempt_queued_at = models.DateTimeField(default=timezone.now)
    retry_at = models.DateTimeField(null=True)
    max_retry_count = models.PositiveSmallIntegerField(default=0)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    # Revocation prevents future attempts without requesting a stop or closing unknown execution.
    source_access_revoked_at = models.DateTimeField(null=True)
    stop_requested_at = models.DateTimeField(null=True)
    closed_at = models.DateTimeField(null=True)
    ended_at = models.DateTimeField(null=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["state", "priority_rank", "attempt_queued_at"],
                name="job_dispatch_order_idx",
            )
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(state__in=JobState.values), name="job_state_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(
                    max_retry_count__lte=3, attempt_count__lte=4, priority_rank__lte=2
                ),
                name="job_attempt_bounds_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        target_executor_id__isnull=False, target_group_id__isnull=True
                    )
                    | models.Q(
                        target_executor_id__isnull=True, target_group_id__isnull=False
                    )
                ),
                name="job_target_exclusive",
            ),
        ]


class ExecutorWorkState(models.Model):
    executor_id: uuid.UUID

    executor = models.OneToOneField(
        "executors.Executor", primary_key=True, on_delete=models.CASCADE
    )
    session_id = models.UUIDField()
    reported_at = models.DateTimeField(default=timezone.now)
    running_run_ids = models.JSONField(default=list)
    local_waiting_count = models.PositiveIntegerField(default=0)
    other_active_run_count = models.PositiveIntegerField(default=0)
    last_assigned_at = models.DateTimeField(null=True)


class Assignment(models.Model):
    job_id: uuid.UUID
    executor_id: uuid.UUID

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="assignments")
    executor = models.ForeignKey("executors.Executor", on_delete=models.PROTECT)
    session_id = models.UUIDField()
    actor_id = models.UUIDField()
    actor_name = models.CharField(max_length=INT_DISPLAY_NAME_SNAPSHOT_MAX_LENGTH)
    computer_name = models.CharField(max_length=128)
    executor_name = models.CharField(max_length=128)
    run_id = models.UUIDField(default=uuid.uuid4, unique=True)
    attempt_number = models.PositiveSmallIntegerField()
    state = models.CharField(
        max_length=max(len(value) for value in AssignmentState.values),
        choices=AssignmentState.choices,
        default=AssignmentState.PREPARING,
    )
    created_at = models.DateTimeField(default=timezone.now)
    permit_expires_at = models.DateTimeField(null=True)
    stop_requested_at = models.DateTimeField(null=True)
    reason = models.CharField(max_length=2000, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(state__in=AssignmentState.values),
                name="assignment_state_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(attempt_number__gte=1, attempt_number__lte=4),
                name="assignment_attempt_valid",
            ),
            models.UniqueConstraint(
                fields=["job"],
                condition=models.Q(
                    state__in=[
                        AssignmentState.PREPARING,
                        AssignmentState.PERMITTED,
                        AssignmentState.RUNNING,
                        AssignmentState.REVIEW,
                    ]
                ),
                name="job_one_active_assignment",
            ),
        ]


class Run(models.Model):
    logs: "RelatedManager[RunLog]"
    job_id: uuid.UUID
    assignment_id: uuid.UUID

    id = models.UUIDField(primary_key=True, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="runs")
    assignment = models.OneToOneField(
        Assignment, on_delete=models.CASCADE, related_name="run"
    )
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True)
    result = models.CharField(
        max_length=max(len(value) for value in RunResult.values),
        choices=RunResult.choices,
        default=RunResult.RUNNING,
    )
    reason = models.CharField(max_length=2000, blank=True)
    outputs_status = models.CharField(
        max_length=max(len(value) for value in OutputsStatus.values),
        choices=OutputsStatus.choices,
        default=OutputsStatus.WAITING,
    )
    outputs = models.JSONField(null=True)
    outputs_reason = models.CharField(max_length=2000, blank=True)
    outputs_unavailable_keys = models.JSONField(default=list)
    error_summary = models.JSONField(null=True)
    logs_complete = models.BooleanField(default=False)
    logs_unavailable_reason = models.CharField(max_length=2000, blank=True)
    log_bytes = models.PositiveBigIntegerField(default=0)
    logs_cleared_at = models.DateTimeField(null=True)
    recording = models.JSONField(default=dict)

    class Meta:
        indexes = [
            models.Index(fields=["-started_at", "-id"], name="run_history_time_idx")
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(result__in=RunResult.values), name="run_result_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(outputs_status__in=OutputsStatus.values),
                name="run_outputs_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(result=RunResult.RUNNING, ended_at__isnull=True)
                    | models.Q(result=RunResult.INTERRUPTED)
                    | models.Q(
                        result__in=[
                            RunResult.COMPLETED,
                            RunResult.ERROR,
                            RunResult.CANCELED,
                            RunResult.TIMED_OUT,
                        ],
                        ended_at__isnull=False,
                    )
                ),
                name="run_result_end_time_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    Exact(
                        models.Func(
                            models.F("outputs_unavailable_keys"),
                            function="jsonb_typeof",
                            output_field=models.CharField(),
                        ),
                        models.Value("array"),
                    )
                )
                & (
                    models.Q(
                        outputs_status__in=[
                            OutputsStatus.WAITING,
                            OutputsStatus.UNAVAILABLE,
                        ],
                        outputs__isnull=True,
                        outputs_unavailable_keys=[],
                    )
                    | (
                        models.Q(outputs__isnull=False)
                        & models.Q(
                            Exact(
                                models.Func(
                                    models.F("outputs"),
                                    function="jsonb_typeof",
                                    output_field=models.CharField(),
                                ),
                                models.Value("array"),
                            )
                        )
                        & (
                            models.Q(
                                outputs_status=OutputsStatus.COMPLETE,
                                outputs_unavailable_keys=[],
                            )
                            | (
                                models.Q(outputs_status=OutputsStatus.PARTIAL)
                                & ~models.Q(outputs_unavailable_keys=[])
                            )
                        )
                    )
                ),
                name="run_outputs_envelope_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(logs_complete=False)
                | models.Q(logs_unavailable_reason=""),
                name="run_logs_completion_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(recording={})
                | (
                    models.Q(recording__has_key="status")
                    & models.Q(recording__status__in=RecordingStatus.values)
                ),
                name="run_recording_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(ended_at__isnull=True)
                | models.Q(ended_at__gte=models.F("started_at")),
                name="run_time_order_valid",
            ),
        ]


class RunLog(models.Model):
    run_id: uuid.UUID

    # The sequence is a receive cursor; log_id remains the source's immutable identity.
    sequence = models.BigAutoField(primary_key=True)
    log_id = models.UUIDField(unique=True)
    run = models.ForeignKey(Run, on_delete=models.CASCADE, related_name="logs")
    timestamp = models.DateTimeField()
    received_at = models.DateTimeField(default=timezone.now)
    level = models.CharField(
        max_length=max(len(entry.value) for entry in RunLogLevel),
        choices=[(entry.value, entry.value) for entry in RunLogLevel],
    )
    message = models.JSONField(null=True)
    user_name = models.TextField()
    machine_name = models.TextField()
    process_name = models.TextField()
    file_name = models.TextField()
    line_no = models.PositiveBigIntegerField()
    project_name = models.TextField()
    custom_fields = models.JSONField(default=dict, blank=True)
    byte_count = models.PositiveIntegerField()

    class Meta:
        indexes = [models.Index(fields=["run", "sequence"], name="run_log_receive_idx")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(level__in=[entry.value for entry in RunLogLevel]),
                name="run_log_level_valid",
            ),
        ]


class RunLogUsage(models.Model):
    organization_id: uuid.UUID

    organization = models.OneToOneField(
        "organizations.Organization", primary_key=True, on_delete=models.CASCADE
    )
    used_bytes = models.PositiveBigIntegerField(default=0)
    group_count = models.PositiveIntegerField(default=0)


class RunFileTransfer(models.Model):
    organization_id: uuid.UUID
    run_id: uuid.UUID

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE
    )
    run = models.ForeignKey("runs.Run", on_delete=models.CASCADE)
    actor_id = models.UUIDField()
    session_id = models.UUIDField()
    kind = models.CharField(
        max_length=max(len(value) for value in RunFileKind.values),
        choices=RunFileKind.choices,
    )
    expires_at = models.DateTimeField()

    class Meta:
        indexes = [
            models.Index(
                fields=["organization", "expires_at"], name="run_transfer_expiry_idx"
            )
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(kind__in=RunFileKind.values),
                name="run_file_kind_valid",
            )
        ]


class RunEvent(models.Model):
    assignment_id: uuid.UUID

    id = models.UUIDField(primary_key=True, editable=False)
    assignment = models.ForeignKey(
        Assignment, on_delete=models.CASCADE, related_name="events"
    )
    kind = models.CharField(
        max_length=max(len(value) for value in RunEventKind.values),
        choices=RunEventKind.choices,
    )
    occurred_at = models.DateTimeField()
    received_at = models.DateTimeField(default=timezone.now)
    reason = models.CharField(max_length=2000, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(kind__in=RunEventKind.values),
                name="run_event_kind_valid",
            )
        ]


class DispatchControl(models.Model):
    # Only the dedicated control worker owns this singleton recovery cycle.
    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    cycle_started_at = models.DateTimeField(default=timezone.now)
    last_tick_at = models.DateTimeField(default=timezone.now)
    recovery_until = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(id=1), name="dispatch_control_singleton"
            )
        ]


class JobAdmissionBudget(models.Model):
    organization = models.OneToOneField(
        "organizations.Organization", primary_key=True, on_delete=models.CASCADE
    )
    tokens = models.FloatField(default=0)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(tokens__gte=0), name="job_admission_tokens_nonnegative"
            )
        ]
