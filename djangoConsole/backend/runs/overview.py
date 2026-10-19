# FileName: overview.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, F, Q, QuerySet, Sum
from django.db.models.functions import TruncDate
from django.http import QueryDict
from django.utils import timezone

from console_project.constants import INT_LIST_PAGE_SIZE
from organizations.permissions import OrganizationAccessContext

from .contracts import RunStatus, INT_MAX_RUN_STATISTICS_DAYS
from .models import Run
from .queries import get_visible_runs


def _get_overview_runs(
    access: OrganizationAccessContext, query: QueryDict, *, statistics: bool
) -> QuerySet[Run]:
    setSingleField = (
        {"project_name", "date_from", "date_until", "executor_page"}
        if statistics
        else {"project_name", "page"}
    )
    if set(query) - setSingleField - {"department_id"}:
        raise ValidationError("Unknown Overview filters.")
    if any(len(query.getlist(strField)) > 1 for strField in setSingleField):
        raise ValidationError("Send each project, date and page only once.")
    runQuery = get_visible_runs(access)
    listDepartmentId = query.getlist("department_id")
    if len(listDepartmentId) > 100:
        raise ValidationError("Select no more than 100 departments.")
    if listDepartmentId:
        runQuery = runQuery.filter(
            job__department_id__in=[uuid.UUID(entry) for entry in listDepartmentId]
        )
    strProjectName = query.get("project_name", "").strip()
    if len(strProjectName) > 128:
        raise ValidationError({"project_name": "Enter no more than 128 characters."})
    if strProjectName:
        runQuery = runQuery.filter(job__project_name__icontains=strProjectName)
    return runQuery


def list_current_runs(access: OrganizationAccessContext, query: QueryDict) -> dict:
    intPage = int(query.get("page", "1"))
    if intPage < 1:
        raise ValidationError({"page": "Select a page greater than zero."})
    runQuery = (
        _get_overview_runs(access, query, statistics=False)
        .filter(status=RunStatus.RUNNING, ended_at__isnull=True)
        .order_by("-started_at", "-id")
        .values(
            "id",
            "started_at",
            project_name=F("job__project_name"),
            project_version=F("job__project_version"),
            executor_id=F("assignment__executor_id"),
            executor_name=F("assignment__executor_name"),
        )
    )
    paginator = Paginator(runQuery, INT_LIST_PAGE_SIZE)
    page = paginator.get_page(intPage)
    return {
        "runs": list(page.object_list),
        "updated_at": timezone.now(),
        "page": page.number,
        "page_size": INT_LIST_PAGE_SIZE,
        "total_count": paginator.count,
        "total_pages": paginator.num_pages,
    }


def get_run_statistics(access: OrganizationAccessContext, query: QueryDict) -> dict:
    intExecutorPage = int(query.get("executor_page", "1"))
    if intExecutorPage < 1:
        raise ValidationError({"executor_page": "Select a page greater than zero."})
    runQuery = _get_overview_runs(access, query, statistics=True)
    dictDate: dict[str, date] = {}
    for strField in ("date_from", "date_until"):
        strDate = query.get(strField, "")
        try:
            selectedDate = date.fromisoformat(strDate)
            if selectedDate.isoformat() != strDate:
                raise ValueError
        except ValueError:
            raise ValidationError({
                strField: "Enter a valid date in YYYY-MM-DD format."
            }) from None
        dictDate[strField] = selectedDate
    intDays = (dictDate["date_until"] - dictDate["date_from"]).days + 1
    if intDays < 1:
        raise ValidationError({
            "date_until": "The end date must not be earlier than the start date."
        })
    if intDays > INT_MAX_RUN_STATISTICS_DAYS:
        raise ValidationError({
            "date_until": f"Select no more than {INT_MAX_RUN_STATISTICS_DAYS} days."
        })
    runZone = ZoneInfo(access.actor.time_zone)
    try:
        fromTime = datetime.combine(dictDate["date_from"], time.min, runZone).astimezone(
            UTC
        )
        untilTime = datetime.combine(
            dictDate["date_until"] + timedelta(days=1), time.min, runZone
        ).astimezone(UTC)
    except OverflowError:
        raise ValidationError(
            "Select dates within the supported calendar range."
        ) from None

    runQuery = (
        runQuery
        .filter(ended_at__isnull=False, ended_at__gte=fromTime, ended_at__lt=untilTime)
        .exclude(status=RunStatus.RUNNING)
        .order_by()
    )
    listEndedStatus = [status for status in RunStatus if status != RunStatus.RUNNING]
    dictResultCount = dict.fromkeys(listEndedStatus, 0)
    dictDailyCount: dict[date, dict[RunStatus, int]] = {}
    totalDuration = timedelta()
    dailyQuery = (
        runQuery
        .annotate(date=TruncDate("ended_at", tzinfo=runZone))
        .values("date", "status")
        .annotate(count=Count("id"), duration=Sum(F("ended_at") - F("started_at")))
        .order_by("date", "status")
    )
    for entry in dailyQuery:
        endedDate = entry["date"]
        status = RunStatus(entry["status"])
        if endedDate not in dictDailyCount:
            dictDailyCount[endedDate] = dict.fromkeys(listEndedStatus, 0)
        dictDailyCount[endedDate][status] = entry["count"]
        dictResultCount[status] += entry["count"]
        totalDuration += entry["duration"]

    # Group by the Executor identity and current name, not per-Run name snapshots.
    executorQuery = (
        runQuery
        .values("assignment__executor_id", "assignment__executor__name")
        .annotate(
            total_count=Count("id"),
            duration=Sum(F("ended_at") - F("started_at")),
            **{
                f"{status}_count": Count("id", filter=Q(status=status))
                for status in listEndedStatus
            },
        )
        .order_by("-total_count", "assignment__executor__name", "assignment__executor_id")
    )
    paginator = Paginator(executorQuery, INT_LIST_PAGE_SIZE)
    page = paginator.get_page(intExecutorPage)
    listExecutor = [
        {
            "id": entry["assignment__executor_id"],
            "name": entry["assignment__executor__name"],
            "total_count": entry["total_count"],
            "duration_seconds": entry["duration"].total_seconds(),
            "results": [
                {"status": status, "count": entry[f"{status}_count"]}
                for status in listEndedStatus
            ],
        }
        for entry in page.object_list
    ]
    return {
        **dictDate,
        "time_zone": access.actor.time_zone,
        "updated_at": timezone.now(),
        "total_count": sum(dictResultCount.values()),
        "total_duration_seconds": totalDuration.total_seconds(),
        "results": [
            {"status": status, "count": intCount}
            for status, intCount in dictResultCount.items()
        ],
        "daily": [
            {
                "date": endedDate,
                "results": [
                    {"status": status, "count": intCount}
                    for status, intCount in dictCount.items()
                ],
            }
            for endedDate, dictCount in dictDailyCount.items()
        ],
        "executors": {
            "entries": listExecutor,
            "page": page.number,
            "page_size": INT_LIST_PAGE_SIZE,
            "total_count": paginator.count,
            "total_pages": paginator.num_pages,
        },
    }
