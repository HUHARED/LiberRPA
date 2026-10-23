# FileName: views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from collections.abc import Callable
from functools import wraps

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.core.paginator import InvalidPage, Paginator
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from accounts.session_revocation import SessionInvalidatedError
from console_project.constants import INT_LIST_PAGE_SIZE
from console_project.http import (
    build_authentication_required_response,
    build_error_response,
    parse_json_request,
)
from executors.models import Executor, ExecutorGroup
from organizations.department_queries import get_department_path, get_department_tree
from organizations.http import (
    get_request_membership,
    lock_request_write_access,
    parse_department_resource_filters,
)
from organizations.contracts import DepartmentRole
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
    build_organization_access,
    get_authorized_departments,
)
from organizations.rate_limits import RequestBudget, request_budget
from packages.contracts import RunSettings
from packages.run_settings import parse_run_settings

from .contracts import (
    ScheduleTimeRequest,
    ScheduleSaveRequest,
    ScheduleEnabledRequest,
    ScheduleDeletionRequest,
)
from .cron import format_cron, preview_triggers
from .models import Schedule
from .services import (
    get_schedule_for_access,
    parse_schedule_time,
    save_schedule,
    set_schedule_enabled,
    delete_schedule,
)


def _handle_errors(view: Callable) -> Callable:
    @wraps(view)
    def wrapped(request: HttpRequest, *args: object, **kwargs: object) -> JsonResponse:
        try:
            return view(request, *args, **kwargs)
        except SessionInvalidatedError:
            return build_authentication_required_response()
        except PermissionDenied:
            return build_error_response(
                "schedule_access_required",
                "Schedule access is unavailable.",
                statusCode=403,
            )
        except ObjectDoesNotExist:
            return build_error_response(
                "schedule_not_found",
                "The Schedule or selected resource is unavailable.",
                statusCode=404,
            )
        except ValidationError as e:
            return build_error_response(
                "invalid_schedule",
                " ".join(e.messages),
                statusCode=400,
                fields=e.message_dict if hasattr(e, "message_dict") else None,
            )
        except InvalidPage:
            return build_error_response(
                "invalid_page", "The requested page is unavailable.", statusCode=400
            )
        except ValueError:
            return build_error_response(
                "invalid_request", "The filter or request is invalid.", statusCode=400
            )

    return wrapped


def _build_payloads(
    schedules: list[Schedule],
    access: OrganizationAccessContext,
    *,
    details: bool = False,
    runSettingsById: dict[uuid.UUID, RunSettings] | None = None,
) -> list[dict[str, object]]:
    if not schedules:
        return []
    dictTree = get_department_tree(access.organization.pk)
    setManageableDepartmentId: set[uuid.UUID] = set(
        get_authorized_departments(access, requiredRole=DepartmentRole.DEVELOPER)
        .filter(pk__in={schedule.department_id for schedule in schedules})
        .values_list("id", flat=True)
    )
    setExecutorId = {
        strExecutorId for schedule in schedules for strExecutorId in schedule.executor_ids
    }
    dictExecutorById: dict[str, Executor] = {
        str(executor.id): executor
        for executor in Executor.objects.filter(pk__in=setExecutorId).only("id", "name")
    }
    dictGroupById: dict[uuid.UUID, ExecutorGroup] = ExecutorGroup.objects.only(
        "id", "name"
    ).in_bulk({
        schedule.group_id for schedule in schedules if schedule.group_id is not None
    })
    listPayload: list[dict[str, object]] = []
    for schedule in schedules:
        creator = schedule.created_by
        group = (
            dictGroupById.get(schedule.group_id)
            if schedule.group_id is not None
            else None
        )
        dictPayload: dict[str, object] = {
            "id": schedule.pk,
            "name": schedule.name,
            "department_id": schedule.department_id,
            "department": {
                "id": schedule.department_id,
                "name": schedule.department.name,
                "path": get_department_path(schedule.department, dictTree),
            },
            "package_id": schedule.package_id,
            "project_name": schedule.package.project_name,
            "project_version": schedule.package.project_version,
            "executor_ids": schedule.executor_ids,
            "executors": [
                {"id": executor.id, "name": executor.name}
                for strExecutorId in schedule.executor_ids
                if (executor := dictExecutorById.get(strExecutorId)) is not None
            ],
            "group_id": schedule.group_id,
            "executor_group": None
            if group is None
            else {"id": group.id, "name": group.name},
            "enabled": schedule.enabled,
            "notes": schedule.notes,
            "cron": format_cron(schedule.cron.split()),
            "run_conflict_policy": schedule.run_conflict_policy,
            "time_zone": schedule.time_zone,
            "active_from": schedule.active_from,
            "active_until": schedule.active_until,
            "created_at": schedule.created_at,
            "created_by": None
            if creator is None
            else {"id": creator.pk, "email": creator.email, "username": creator.username},
            "can_manage": schedule.department_id in setManageableDepartmentId,
        }
        if details:
            runSettings = (
                runSettingsById.get(schedule.pk) if runSettingsById is not None else None
            )
            if runSettings is None:
                runSettings = parse_run_settings(schedule)
            dictPayload["settings"] = runSettings.model_dump(mode="json")
            dictPayload["python_environment_name"] = (
                schedule.package.python_environment_name
            )
            dictPayload["upcoming_triggers"] = preview_triggers(
                schedule.cron,
                schedule.time_zone,
                schedule.active_from,
                schedule.active_until,
                timezone.now(),
            )
        listPayload.append(dictPayload)

    return listPayload


@never_cache
@require_http_methods(["GET", "POST"])
@_handle_errors
def list_or_create_schedules(request: HttpRequest) -> JsonResponse:
    membership = get_request_membership(request)
    if isinstance(membership, JsonResponse):
        return membership
    if request.method == "POST":
        form = parse_json_request(
            request, ScheduleSaveRequest, maxBodyBytes=2 * 1024 * 1024
        )
        if isinstance(form, JsonResponse):
            return form
        with transaction.atomic():
            access = lock_request_write_access(request, membership)
            schedule = save_schedule(access, form)
            return JsonResponse(
                {
                    "schedule": _build_payloads(
                        [schedule],
                        access,
                        details=True,
                        runSettingsById={schedule.pk: form.settings},
                    )[0]
                },
                status=201,
            )
    access = build_organization_access(membership, channel=AccessChannel.SESSION)
    filters = parse_department_resource_filters(
        request.GET, extraFields=frozenset({"enabled", "project_name", "target"})
    )
    query = Schedule.objects.filter(
        deleted_at__isnull=True,
        department__in=get_authorized_departments(
            access, requiredRole=DepartmentRole.OPERATOR
        ),
    ).select_related("department", "package", "created_by")
    if filters["departmentIds"]:
        query = query.filter(department_id__in=filters["departmentIds"])
    if filters["name"]:
        query = query.filter(name__icontains=filters["name"])
    if request.GET.get("project_name"):
        query = query.filter(package__project_name__icontains=request.GET["project_name"])
    if request.GET.get("enabled"):
        if request.GET["enabled"] not in ("true", "false"):
            raise ValueError("Invalid Enabled filter.")
        query = query.filter(enabled=request.GET["enabled"] == "true")
    if request.GET.get("target"):
        targetId = uuid.UUID(request.GET["target"])
        from django.db.models import Q

        query = query.filter(
            Q(group_id=targetId) | Q(executor_ids__contains=[str(targetId)])
        )
    paginator = Paginator(query.order_by("name", "id"), INT_LIST_PAGE_SIZE)
    page = paginator.page(filters["pageNumber"])
    return JsonResponse({
        "schedules": _build_payloads(list(page.object_list), access),
        "page": page.number,
        "page_size": INT_LIST_PAGE_SIZE,
        "total_count": paginator.count,
        "total_pages": paginator.num_pages,
    })


@never_cache
@require_http_methods(["GET", "POST"])
@_handle_errors
def get_or_update_schedule(request: HttpRequest, scheduleId: uuid.UUID) -> JsonResponse:
    membership = get_request_membership(request)
    if isinstance(membership, JsonResponse):
        return membership
    if request.method == "POST":
        form = parse_json_request(
            request, ScheduleSaveRequest, maxBodyBytes=2 * 1024 * 1024
        )
        if isinstance(form, JsonResponse):
            return form
        with transaction.atomic():
            access = lock_request_write_access(request, membership)
            schedule = get_schedule_for_access(access, scheduleId, forUpdate=True)
            schedule = save_schedule(access, form, schedule=schedule)
            return JsonResponse({
                "schedule": _build_payloads(
                    [schedule],
                    access,
                    details=True,
                    runSettingsById={schedule.pk: form.settings},
                )[0]
            })
    access = build_organization_access(membership, channel=AccessChannel.SESSION)
    return JsonResponse({
        "schedule": _build_payloads(
            [get_schedule_for_access(access, scheduleId)], access, details=True
        )[0]
    })


@never_cache
@require_POST
@_handle_errors
def change_schedule_enabled(
    request: HttpRequest,
    scheduleId: uuid.UUID,
) -> JsonResponse:
    membership = get_request_membership(request)
    if isinstance(membership, JsonResponse):
        return membership
    form = parse_json_request(request, ScheduleEnabledRequest)
    if isinstance(form, JsonResponse):
        return form
    with transaction.atomic():
        access = lock_request_write_access(request, membership)
        schedule = get_schedule_for_access(access, scheduleId, forUpdate=True)
        set_schedule_enabled(access, schedule, form.enabled)
        return JsonResponse({
            "schedule": _build_payloads([schedule], access, details=True)[0]
        })


@never_cache
@require_POST
@_handle_errors
def delete_schedule_record(request: HttpRequest, scheduleId: uuid.UUID) -> JsonResponse:
    membership = get_request_membership(request)
    if isinstance(membership, JsonResponse):
        return membership
    form = parse_json_request(request, ScheduleDeletionRequest)
    if isinstance(form, JsonResponse):
        return form
    with transaction.atomic():
        access = lock_request_write_access(request, membership)
        delete_schedule(
            access, get_schedule_for_access(access, scheduleId, forUpdate=True)
        )
        return JsonResponse({
            "message": "Schedule deleted. Accepted Jobs continue independently."
        })


@request_budget(RequestBudget.READ, methods=("POST",))
@never_cache
@require_POST
@_handle_errors
def preview_schedule(request: HttpRequest) -> JsonResponse:
    membership = get_request_membership(request)
    if isinstance(membership, JsonResponse):
        return membership
    build_organization_access(membership, channel=AccessChannel.SESSION)
    form = parse_json_request(request, ScheduleTimeRequest)
    if isinstance(form, JsonResponse):
        return form
    strCron, activeFrom, activeUntil = parse_schedule_time(form)
    return JsonResponse({
        "normalized_cron": strCron,
        "upcoming_triggers": preview_triggers(
            strCron, form.time_zone, activeFrom, activeUntil, timezone.now()
        ),
    })
