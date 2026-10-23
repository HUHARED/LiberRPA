# FileName: email_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging
import uuid
from datetime import datetime, time, timedelta
from typing import cast
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.core.paginator import InvalidPage, Paginator
from django.db import DatabaseError
from django.db.models import Count, F, Q, Window
from django.db.models.functions import RowNumber
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from pydantic import ValidationError as ContractValidationError
from pydantic_core import PydanticSerializationError

from console_project.config import LimitsConfig
from console_project.constants import INT_LIST_PAGE_SIZE
from console_project.contracts import PaginationResponse
from console_project.http import (
    build_error_response,
    build_authentication_required_response,
    build_service_unavailable_response,
    parse_page_number,
)
from console_project.validators import parse_date_range
from notifications.contracts import EmailStatus, EmailReasonCode, TUPLE_EMAIL_ISSUE_STATUS
from notifications.models import EmailType, EmailDelivery
from notifications.delivery import EMAIL_BUDGET_WINDOW

from .access import get_platform_actor
from .contracts import (
    EmailIssueResponse,
    EmailUsageResponse,
    EmailIssueListResponse,
    EmailIssueOrganizationResponse,
    EmailIssueStatusResponse,
    EmailIssueFiltersResponse,
)

_LOGGER = logging.getLogger("console.operations")


def _build_email_error_response(error: Exception) -> JsonResponse:
    if isinstance(error, PermissionDenied):
        return build_error_response(
            "platform_access_required",
            "Platform administrator access is required.",
            statusCode=403,
        )
    if isinstance(error, InvalidPage):
        return build_error_response(
            "email_issue_page_not_found", "Email issue page not found.", statusCode=404
        )
    if isinstance(error, (ImproperlyConfigured, DatabaseError)):
        return build_service_unavailable_response()
    _LOGGER.exception("Could not build the email diagnostics response.")
    return build_error_response(
        "internal_server_error",
        "The service could not build a valid response.",
        statusCode=500,
    )


@never_cache
@require_GET
def list_email_issues(request: HttpRequest) -> JsonResponse:
    """Read instance-wide email usage and filtered issues without loading message bodies or private proofs."""
    try:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        actor = get_platform_actor(request)
        displayZone = ZoneInfo(actor.time_zone)
        query = request.GET
        try:
            setSingleField = {"page", "date_from", "date_to"}
            setMultipleField = {"organization_id", "status"}
            if set(query) - setSingleField - setMultipleField:
                raise ValueError("Unknown email filters.")
            if any(len(query.getlist(key)) > 1 for key in setSingleField):
                raise ValueError("Send each date and page only once.")
            if any(len(query.getlist(key)) > 100 for key in setMultipleField):
                raise ValueError("Too many email filters.")
            intPage = parse_page_number(query)
            fromTime, untilTime = parse_date_range(
                query.get("date_from"), query.get("date_to"), displayZone
            )
            listOrganization = query.getlist("organization_id")
            listOrganizationId = [
                uuid.UUID(value) for value in listOrganization if value != "none"
            ]
            listStatus = [EmailStatus(value) for value in query.getlist("status")]
            if any(status not in TUPLE_EMAIL_ISSUE_STATUS for status in listStatus):
                raise ValueError("Select an email issue status.")
        except ValidationError as e:
            return build_error_response(
                "invalid_email_filters",
                "Some email filters are invalid.",
                statusCode=400,
                fields=e.message_dict,
            )
        except ValueError:
            return build_error_response(
                "invalid_email_filters",
                "Select valid email filters and a valid page.",
                statusCode=400,
            )

        issues = EmailDelivery.objects.filter(status__in=TUPLE_EMAIL_ISSUE_STATUS)
        if fromTime is not None:
            issues = issues.filter(finished_at__gte=fromTime)
        if untilTime is not None:
            issues = issues.filter(finished_at__lt=untilTime)
        if listOrganization:
            organizationCondition = Q(organization_id__in=listOrganizationId)
            if "none" in listOrganization:
                organizationCondition |= Q(organization_id__isnull=True)
            issues = issues.filter(organizationCondition)
        if listStatus:
            issues = issues.filter(status__in=listStatus)
        page = Paginator(issues.order_by("-finished_at", "-id"), INT_LIST_PAGE_SIZE).page(
            intPage
        )

        currentTime = timezone.now()
        today = timezone.localdate(currentTime, displayZone)
        dayStart = datetime.combine(today, time.min, displayZone)
        dayEnd = datetime.combine(today + timedelta(days=1), time.min, displayZone)
        limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
        # Match the worker's strict rolling cutoff; list filters never affect these counts.
        recentAttempts = Q(attempted_at__gt=currentTime - EMAIL_BUDGET_WINDOW)
        pendingDeliveries = Q(status=EmailStatus.PENDING)
        failedToday = Q(
            status=EmailStatus.FAILED,
            finished_at__gte=dayStart,
            finished_at__lt=dayEnd,
        )
        dictUsage = EmailDelivery.objects.filter(
            recentAttempts | pendingDeliveries | failedToday
        ).aggregate(
            smtp_budget_used_24h=Count("pk", filter=recentAttempts),
            run_budget_used_24h=Count(
                "pk", filter=recentAttempts & Q(email_type=EmailType.RUN)
            ),
            accepted_by_smtp_24h=Count(
                "pk", filter=recentAttempts & Q(status=EmailStatus.ACCEPTED)
            ),
            pending=Count("pk", filter=pendingDeliveries),
            failed_today=Count("pk", filter=failedToday),
        )
        # These completed rows contain only bounded metadata; the dialog uses the same snapshot.
        response = EmailIssueListResponse(
            issues=[
                EmailIssueResponse(
                    id=delivery.id,
                    organization_id=delivery.organization_id,
                    organization_name=delivery.organization_name,
                    email_type_label=str(EmailType(delivery.email_type).label),
                    recipient=delivery.recipient,
                    status=EmailStatus(delivery.status),
                    status_label=str(EmailStatus(delivery.status).label),
                    created_at=delivery.created_at,
                    attempted_at=delivery.attempted_at,
                    # The issue-state database constraint requires a finished time.
                    finished_at=cast(datetime, delivery.finished_at),
                    reason_code=EmailReasonCode(delivery.reason_code),
                    reason_text=str(EmailReasonCode(delivery.reason_code).label),
                )
                for delivery in page
            ],
            pagination=PaginationResponse(
                page=page.number,
                page_size=INT_LIST_PAGE_SIZE,
                total_count=page.paginator.count,
                total_pages=page.paginator.num_pages,
            ),
            usage=EmailUsageResponse(
                smtp_budget_used_24h=dictUsage["smtp_budget_used_24h"],
                smtp_budget_limit_24h=limits.maxEmailRecipientsPer24Hours,
                run_budget_used_24h=dictUsage["run_budget_used_24h"],
                run_budget_limit_24h=limits.maxRunEmailRecipientsPer24Hours,
                accepted_by_smtp_24h=dictUsage["accepted_by_smtp_24h"],
                pending=dictUsage["pending"],
            ),
            failed_today=dictUsage["failed_today"],
            time_zone=str(displayZone),
            today=today,
            updated_at=currentTime,
        )
        return JsonResponse(response.model_dump(mode="python"))
    except (
        PermissionDenied,
        InvalidPage,
        ImproperlyConfigured,
        DatabaseError,
        ValueError,
        ContractValidationError,
        PydanticSerializationError,
    ) as e:
        return _build_email_error_response(e)


@never_cache
@require_GET
def get_email_issue_filters(request: HttpRequest) -> JsonResponse:
    """Offer organization identities from retained issues, including deleted organizations."""
    try:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        get_platform_actor(request)
        if request.GET:
            return build_error_response(
                "invalid_email_filters",
                "This request does not accept filters.",
                statusCode=400,
            )
        organizations = (
            EmailDelivery.objects
            .filter(status__in=TUPLE_EMAIL_ISSUE_STATUS)
            .annotate(
                organizationPosition=Window(
                    expression=RowNumber(),
                    partition_by=[F("organization_id")],
                    order_by=[F("finished_at").desc(), F("id").desc()],
                )
            )
            .filter(organizationPosition=1)
            .order_by("organization_name", "organization_id")
            .values_list("organization_id", "organization_name")
        )
        response = EmailIssueFiltersResponse(
            organizations=[
                EmailIssueOrganizationResponse(
                    id=organizationId,
                    name=strName
                    if organizationId is not None
                    else "Without organization",
                )
                for organizationId, strName in organizations
            ],
            statuses=[
                EmailIssueStatusResponse(value=status, label=str(status.label))
                for status in TUPLE_EMAIL_ISSUE_STATUS
            ],
        )
        return JsonResponse(response.model_dump(mode="python"))
    except (
        PermissionDenied,
        ImproperlyConfigured,
        DatabaseError,
        ContractValidationError,
        PydanticSerializationError,
    ) as e:
        return _build_email_error_response(e)
