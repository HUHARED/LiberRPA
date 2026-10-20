# FileName: services.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from datetime import datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Value
from django.db.models.functions import Lower
from django.utils import timezone

from console_project.validators import parse_zoned_time
from executors.models import Executor, ExecutorGroup
from operations.audit import get_audit_snapshot, record_audit
from organizations.contracts import DepartmentRole
from organizations.limits import get_organization_limits
from organizations.permissions import (
    OrganizationAccessContext,
    get_authorized_departments,
)
from packages.models import Package
from packages.runtime import (
    parse_run_settings,
    apply_run_settings,
    validate_run_settings,
)

from .contracts import ScheduleTimeRequest, ScheduleSaveRequest
from .cron import format_cron, normalize_cron, get_schedule_zone, get_next_trigger
from .models import Schedule


def get_schedule_for_access(
    access: OrganizationAccessContext, scheduleId: uuid.UUID, *, forUpdate: bool = False
) -> Schedule:
    query = Schedule.objects.filter(
        deleted_at__isnull=True,
        department__in=get_authorized_departments(
            access, requiredRole=DepartmentRole.OPERATOR
        ),
    )
    if forUpdate:
        query = query.select_for_update(of=("self",))
    return query.select_related("department", "package", "created_by").get(pk=scheduleId)


def require_schedule_management(
    access: OrganizationAccessContext, departmentId: uuid.UUID
) -> None:
    if (
        not get_authorized_departments(access, requiredRole=DepartmentRole.DEVELOPER)
        .filter(pk=departmentId)
        .exists()
    ):
        raise PermissionDenied("Developer access is required to manage Schedules.")


def parse_schedule_time(
    timeRequest: ScheduleTimeRequest,
) -> tuple[str, datetime, datetime]:
    strCron = normalize_cron(timeRequest.cron)
    get_schedule_zone(timeRequest.time_zone)
    activeFrom = parse_zoned_time(timeRequest.active_from, timeRequest.time_zone)
    activeUntil = parse_zoned_time(timeRequest.active_until, timeRequest.time_zone)
    if activeUntil <= activeFrom:
        raise ValidationError({
            "active_until": "Active Until must be later than Active From."
        })
    return strCron, activeFrom, activeUntil


def save_schedule(
    access: OrganizationAccessContext,
    form: ScheduleSaveRequest,
    *,
    schedule: Schedule | None = None,
) -> Schedule:
    def validate_targets(
        departmentId: uuid.UUID, executorIds: list[uuid.UUID], groupId: uuid.UUID | None
    ) -> None:
        if (groupId is None) == (not executorIds) or len(executorIds) != len(
            set(executorIds)
        ):
            raise ValidationError("Select distinct Executors or one Executor Group.")
        if groupId is not None:
            if not ExecutorGroup.objects.filter(
                pk=groupId, department_id=departmentId, deleted_at__isnull=True
            ).exists():
                raise ValidationError({"group_id": "Select a group in this department."})
        elif Executor.objects.filter(
            pk__in=executorIds, department_id=departmentId, deleted_at__isnull=True
        ).count() != len(executorIds):
            raise ValidationError({
                "executor_ids": "Select current Executors in this department."
            })

    departmentId = form.department_id
    if schedule is not None:
        require_schedule_management(access, schedule.department_id)
    if schedule is None or schedule.department_id != departmentId:
        require_schedule_management(access, departmentId)
    strCron, activeFrom, activeUntil = parse_schedule_time(form)
    package = Package.objects.select_related("department").get(
        pk=form.package_id, department_id=departmentId
    )
    validate_targets(departmentId, form.executor_ids, form.group_id)
    runSettings = validate_run_settings(package, form.settings)
    boolCreated = schedule is None
    boolSettingsChanged = (
        schedule is not None and parse_run_settings(schedule) != runSettings
    )
    dictBefore = {} if schedule is None else get_audit_snapshot(schedule)
    if schedule is None:
        limits = get_organization_limits(access.organization)
        intCount = Schedule.objects.filter(
            department__organization=access.organization, deleted_at__isnull=True
        ).count()
        if intCount >= limits.maxSchedulesPerOrganization:
            raise ValidationError(
                "This organization has reached its Schedule limit.",
                code="schedule_count_limit",
            )
        schedule = Schedule(department_id=departmentId, created_by=access.actor)
    boolResetTime = (
        boolCreated
        or (form.enabled and not schedule.enabled)
        or (
            format_cron(schedule.cron.split()),
            schedule.time_zone,
            schedule.active_from,
            schedule.active_until,
        )
        != (strCron, form.time_zone, activeFrom, activeUntil)
    )
    schedule.name = form.name.strip()
    if not schedule.name or "\x00" in schedule.name or "\x00" in form.notes:
        raise ValidationError("Use a nonempty name and text without null characters.")
    schedule.notes = form.notes
    schedule.department = package.department
    schedule.package = package
    schedule.executor_ids = [str(executorId) for executorId in form.executor_ids]
    schedule.group_id = form.group_id
    apply_run_settings(schedule, runSettings)
    schedule.enabled = form.enabled
    schedule.cron = strCron
    schedule.time_zone = form.time_zone
    schedule.active_from = activeFrom
    schedule.active_until = activeUntil
    schedule.updated_at = timezone.now()
    if not schedule.enabled:
        schedule.next_trigger_at = None
    elif boolResetTime:
        schedule.next_trigger_at = get_next_trigger(
            strCron, form.time_zone, activeFrom, activeUntil, schedule.updated_at
        )
    if (
        Schedule.objects
        .filter(department_id=departmentId, deleted_at__isnull=True)
        .exclude(pk=schedule.pk)
        .alias(name_key=Lower("name"))
        .filter(name_key=Lower(Value(schedule.name)))
        .exists()
    ):
        raise ValidationError({
            "name": "A Schedule with this name already exists in this department."
        })
    schedule.save()
    from packages.preparation import request_package_preparation
    from executors.models import ExecutorGroupMember

    listExecutorId = (
        form.executor_ids
        if form.group_id is None
        else list(
            ExecutorGroupMember.objects.filter(group_id=form.group_id).values_list(
                "executor_id", flat=True
            )
        )
    )
    request_package_preparation(package, listExecutorId)
    record_audit(
        "schedule.create" if boolCreated else "schedule.update",
        actor=access.actor,
        organization=access.organization,
        target=schedule,
        channel=access.channel,
        before=dictBefore,
        metadata={"run_settings_changed": True} if boolSettingsChanged else None,
    )
    return schedule


def set_schedule_enabled(
    access: OrganizationAccessContext, schedule: Schedule, enabled: bool
) -> None:
    require_schedule_management(access, schedule.department_id)
    if schedule.enabled == enabled:
        return
    dictBefore = get_audit_snapshot(schedule)
    schedule.enabled = enabled
    schedule.updated_at = timezone.now()
    schedule.next_trigger_at = (
        get_next_trigger(
            schedule.cron,
            schedule.time_zone,
            schedule.active_from,
            schedule.active_until,
            schedule.updated_at,
        )
        if enabled
        else None
    )
    schedule.save(update_fields=["enabled", "updated_at", "next_trigger_at"])
    record_audit(
        "schedule.enable" if enabled else "schedule.disable",
        actor=access.actor,
        organization=access.organization,
        target=schedule,
        before=dictBefore,
    )


def delete_schedule(access: OrganizationAccessContext, schedule: Schedule) -> None:
    require_schedule_management(access, schedule.department_id)
    schedule.enabled = False
    schedule.next_trigger_at = None
    schedule.deleted_at = timezone.now()
    schedule.updated_at = schedule.deleted_at
    schedule.save(
        update_fields=["enabled", "next_trigger_at", "deleted_at", "updated_at"]
    )
    # Accepted Jobs retain their independent snapshot and continue until explicitly controlled.
    record_audit(
        "schedule.delete",
        actor=access.actor,
        organization=access.organization,
        target=schedule,
    )
