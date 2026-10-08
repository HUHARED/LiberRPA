# FileName: queries.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from collections.abc import Iterable, Mapping

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import QuerySet
from django.http import QueryDict

from console_project.validators import parse_zoned_time
from organizations.models import Department, DepartmentRole
from organizations.department_queries import get_department_path
from organizations.permissions import (
    OrganizationAccessContext,
    get_authorized_departments,
)

from .models import Assignment, AssignmentState, Job, JobState, Run, RunResult

_INT_PAGE_SIZE = 50
_INT_MAX_SELECTED_RUNS = 20000
_DICT_PRIORITY_NAME = {0: "high", 1: "normal", 2: "low"}


def get_visible_jobs(access: OrganizationAccessContext) -> QuerySet[Job]:
    jobQuery = Job.objects.filter(request__organization=access.organization)
    if not access.isOrgAdmin:
        jobQuery = jobQuery.filter(
            department__in=get_authorized_departments(
                access, requiredRole=DepartmentRole.OPERATOR
            )
        )
    return jobQuery.select_related("request")


def get_visible_runs(access: OrganizationAccessContext) -> QuerySet[Run]:
    runQuery = Run.objects.filter(job__request__organization=access.organization)
    if not access.isOrgAdmin:
        runQuery = runQuery.filter(
            job__department__in=get_authorized_departments(
                access, requiredRole=DepartmentRole.OPERATOR
            )
        )
    return runQuery.select_related("job__request", "assignment")


def get_history_departments(access: OrganizationAccessContext) -> list[dict]:
    dictDepartment = {
        entry.id: entry
        for entry in Department.objects.filter(organization=access.organization)
    }
    setVisibleId = (
        set(dictDepartment)
        if access.isOrgAdmin
        else set(
            get_authorized_departments(
                access, requiredRole=DepartmentRole.OPERATOR
            ).values_list("id", flat=True)
        )
    )
    return sorted(
        [
            {
                "id": entry.id,
                "name": entry.name,
                "path": get_department_path(entry, dictDepartment),
                "deleted_at": entry.deleted_at,
            }
            for entry in dictDepartment.values()
            if entry.id in setVisibleId
        ],
        key=lambda entry: (entry["path"].casefold(), str(entry["id"])),
    )


def _get_active_assignments(jobIds: list[uuid.UUID]) -> dict[uuid.UUID, Assignment]:
    if not jobIds:
        return {}
    # The database permits only one active Assignment per Job.
    return {
        assignment.job_id: assignment
        for assignment in Assignment.objects.filter(
            job_id__in=jobIds,
            state__in=(
                AssignmentState.PREPARING,
                AssignmentState.PERMITTED,
                AssignmentState.RUNNING,
                AssignmentState.REVIEW,
            ),
        ).only("job_id", "executor_id", "executor_name")
    }


def build_job_payload(
    job: Job,
    *,
    details: bool = False,
    assignmentsByJobId: Mapping[uuid.UUID, Assignment] | None = None,
) -> dict[str, object]:
    if assignmentsByJobId is None:
        assignmentsByJobId = _get_active_assignments([job.id])
    assignment = assignmentsByJobId.get(job.id)
    dictPayload: dict[str, object] = {
        "id": job.id,
        "job_request_id": job.request_id,
        "department_id": job.department_id,
        "source": job.request.source,
        "schedule_id": job.request.schedule_id,
        "schedule_name": job.request.schedule_name,
        "scheduled_at": job.request.scheduled_at,
        "project_name": job.project_name,
        "version": job.version,
        "package_id": job.package_id,
        "target_type": "group" if job.target_group_id else "executor",
        "target_id": job.target_group_id or job.target_executor_id,
        "target_name": job.target_name,
        "executor_id": assignment.executor_id if assignment else None,
        "executor_name": assignment.executor_name if assignment else None,
        "priority": _DICT_PRIORITY_NAME[job.priority],
        "state": job.state,
        "reason": job.reason,
        "queued_at": job.queued_at,
        "retry_at": job.retry_at,
        "closed_at": job.closed_at,
        "ended_at": job.ended_at,
        "can_cancel": job.stop_requested_at is None
        and job.state
        in (JobState.WAITING, JobState.PREPARING, JobState.STARTING, JobState.RETRY),
        "can_stop": job.stop_requested_at is None
        and job.state in (JobState.RUNNING, JobState.REVIEW),
        "can_close": job.state == JobState.REVIEW,
    }
    if details:
        dictPayload.update({
            "inputs": job.inputs,
            "runs": [
                build_run_payload(run)
                for run in job.runs.select_related("assignment", "job__request").order_by(
                    "assignment__attempt"
                )
            ],
            "events": [
                {
                    "kind": entry["events__kind"],
                    "occurred_at": entry["events__occurred_at"],
                    "reason": entry["events__reason"],
                }
                for entry in job.assignments
                .values("events__kind", "events__occurred_at", "events__reason")
                .exclude(events__isnull=True)
                .order_by("events__occurred_at")
            ],
        })
    return dictPayload


def build_job_payloads(jobs: Iterable[Job]) -> list[dict[str, object]]:
    listJob = list(jobs)
    dictAssignmentByJobId = _get_active_assignments([job.id for job in listJob])
    return [
        build_job_payload(job, assignmentsByJobId=dictAssignmentByJobId)
        for job in listJob
    ]


def build_run_payload(run: Run, *, details: bool = False) -> dict[str, object]:
    job = run.job
    assignment = run.assignment
    dictPayload: dict[str, object] = {
        "id": run.id,
        "job_id": run.job_id,
        "department_id": job.department_id,
        "schedule_name": job.request.schedule_name,
        "project_name": job.project_name,
        "version": job.version,
        "executor_id": assignment.executor_id,
        "executor_name": assignment.executor_name,
        "account_name": assignment.actor_name,
        "computer": assignment.computer,
        "attempt": assignment.attempt,
        "started_at": run.started_at,
        "ended_at": run.ended_at,
        "result": run.result,
        "reason": run.reason,
        "outputs_status": run.outputs_status,
        "can_stop": run.ended_at is None
        and job.state != JobState.FINISHED
        and assignment.stop_requested_at is None,
    }
    if details:
        from .transfers import build_run_file_availability

        dictDepartmentById: dict[uuid.UUID, Department] = (
            Department.objects
            .filter(organization_id=job.request.organization_id)
            .only("id", "parent_id", "name", "deleted_at")
            .in_bulk()
        )
        department = dictDepartmentById[job.department_id]
        dictPayload.update({
            "department_path": get_department_path(department, dictDepartmentById),
            "department_deleted_at": department.deleted_at,
            "files": build_run_file_availability(run),
            "inputs": job.inputs,
            "outputs": run.outputs,
            "outputs_reason": run.outputs_reason,
            "outputs_unavailable_keys": run.outputs_unavailable_keys,
            "error_summary": run.error_summary,
            "job": build_job_payload(job),
            "logs_cleared_at": run.logs_cleared_at,
            "recording": run.recording,
            "other_runs": [
                build_run_payload(otherRun)
                for otherRun in job.runs
                .exclude(pk=run.id)
                .select_related("assignment", "job__request")
                .order_by("assignment__attempt")
            ],
        })
    return dictPayload


def _get_filtered_work(
    access: OrganizationAccessContext, query: QueryDict, *, runs: bool
) -> QuerySet[Job | Run]:
    strPrefix = "job__" if runs else ""
    workQuery: QuerySet[Job | Run] = (
        get_visible_runs(access)
        if runs
        else get_visible_jobs(access).exclude(state=JobState.FINISHED)
    )
    listDepartmentId = query.getlist("department_id")
    if listDepartmentId:
        workQuery = workQuery.filter(**{
            f"{strPrefix}department_id__in": [
                uuid.UUID(entry) for entry in listDepartmentId
            ]
        })
    for strField in ("project_name", "schedule_name"):
        strValue = query.get(strField, "").strip()
        if strValue:
            strLookup = (
                f"{strPrefix}request__schedule_name__icontains"
                if strField == "schedule_name"
                else f"{strPrefix}project_name__icontains"
            )
            workQuery = workQuery.filter(**{strLookup: strValue})
    strExecutorId = query.get("executor_id", "")
    if strExecutorId:
        workQuery = workQuery.filter(**{
            "assignment__executor_id" if runs else "target_executor_id": uuid.UUID(
                strExecutorId
            )
        })
    listStatus = query.getlist("result" if runs else "state")
    if listStatus:
        setAllowed = set(RunResult.values if runs else JobState.values)
        if not set(listStatus).issubset(setAllowed):
            raise ValidationError("Unknown status filter.", code="invalid_filter")
        workQuery = workQuery.filter(**{
            "result__in" if runs else "state__in": listStatus
        })
    if runs:
        for strQueryKey, strLookup in (
            ("started_from", "started_at__gte"),
            ("started_until", "started_at__lt"),
        ):
            strTime = query.get(strQueryKey, "")
            if strTime:
                workQuery = workQuery.filter(**{
                    strLookup: parse_zoned_time(strTime, access.actor.time_zone)
                })
    return (
        workQuery.order_by("-started_at", "-id")
        if runs
        else workQuery.order_by("priority", "queued_at", "id")
    )


def get_matching_run_ids(
    access: OrganizationAccessContext, query: QueryDict
) -> list[uuid.UUID]:
    # Read one bounded ID set; separate count and page queries could see different runs.
    listRunId: list[uuid.UUID] = list(
        _get_filtered_work(access, query, runs=True).values_list("id", flat=True)[
            : _INT_MAX_SELECTED_RUNS + 1
        ]
    )
    if len(listRunId) > _INT_MAX_SELECTED_RUNS:
        raise ValidationError(
            f"Narrow the filters before selecting all runs (maximum {_INT_MAX_SELECTED_RUNS:,}).",
            code="run_selection_too_large",
        )
    return listRunId


def list_work(access: OrganizationAccessContext, query: QueryDict, *, runs: bool) -> dict:
    workQuery = _get_filtered_work(access, query, runs=runs)
    intPage = int(query.get("page", "1"))
    paginator: Paginator[Job | Run] = Paginator(workQuery, _INT_PAGE_SIZE)
    page = paginator.page(intPage)
    listWork = list(page.object_list)
    dictAssignmentByJobId = (
        _get_active_assignments([entry.id for entry in listWork]) if not runs else {}
    )
    return {
        "runs" if runs else "jobs": [
            (
                build_run_payload(entry)
                if isinstance(entry, Run)
                else build_job_payload(entry, assignmentsByJobId=dictAssignmentByJobId)
            )
            for entry in listWork
        ],
        "page": page.number,
        "page_size": _INT_PAGE_SIZE,
        "total_count": paginator.count,
        "total_pages": paginator.num_pages,
    }
