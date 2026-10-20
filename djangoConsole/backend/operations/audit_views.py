# FileName: audit_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import json
import logging
import re
import uuid
from datetime import date, datetime, time, timedelta
from typing import cast
from zoneinfo import ZoneInfo

from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.core.paginator import InvalidPage
from django.db import DatabaseError
from django.http import HttpRequest, JsonResponse, QueryDict
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from pydantic import ValidationError as ContractValidationError
from pydantic_core import PydanticSerializationError

from accounts.models import User
from console_project.http import (
    build_error_response,
    build_authentication_required_response,
    build_service_unavailable_response,
    parse_page_number,
)
from console_project.validators import validate_time_zone
from organizations.permissions import AccessChannel, get_current_membership
from organizations.rate_limits import check_request_budget

from .audit_queries import (
    AuditListFilters,
    get_audit_list,
    get_audit_filter_options,
    get_audit_details,
)
from .contracts import (
    AuditResult,
    AuditStage,
    AuditListResponse,
    AuditFilterOptionsResponse,
    AuditDetailsResponse,
)
from .models import AuditRecord

_LOGGER = logging.getLogger("console.operations")


def _parse_audit_filters(query: QueryDict, defaultTimeZone: str) -> AuditListFilters:
    setSingleField = {"page", "date_from", "date_to", "time_zone"}
    setMultipleField = {"actor_id", "module", "action", "result"}
    if set(query) - setSingleField - setMultipleField:
        raise ValueError("Unknown audit filters.")
    if any(len(query.getlist(strField)) > 1 for strField in setSingleField):
        raise ValueError("Send each date, time zone and page only once.")
    # Match the existing resource filters' bound on repeated selections.
    if any(len(query.getlist(strField)) > 100 for strField in setMultipleField):
        raise ValueError("Too many filter values.")
    strTimeZone = query.get("time_zone", defaultTimeZone)
    try:
        validate_time_zone(strTimeZone)
    except ValidationError as e:
        raise ValidationError({"time_zone": e.messages}) from None
    auditZone = ZoneInfo(strTimeZone)
    dictDate: dict[str, date] = {}
    for strField in ("date_from", "date_to"):
        strDate = query.get(strField)
        if strDate is None:
            continue
        try:
            if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", strDate) is None:
                raise ValueError
            dictDate[strField] = date.fromisoformat(strDate)
        except ValueError:
            raise ValidationError({
                strField: "Enter a valid date in YYYY-MM-DD format."
            }) from None
    if (
        "date_from" in dictDate
        and "date_to" in dictDate
        and dictDate["date_from"] > dictDate["date_to"]
    ):
        raise ValidationError({
            "date_to": "The end date must not be earlier than the start date."
        })
    fromTime = (
        datetime.combine(dictDate["date_from"], time.min, auditZone)
        if "date_from" in dictDate
        else None
    )
    try:
        # The inclusive end date becomes the next local midnight, including 23/25-hour days.
        untilTime = (
            datetime.combine(dictDate["date_to"] + timedelta(days=1), time.min, auditZone)
            if "date_to" in dictDate
            else None
        )
    except OverflowError:
        raise ValidationError({"date_to": "Select an earlier end date."}) from None
    listActor = query.getlist("actor_id")
    tupleActorId = tuple(
        uuid.UUID(strValue) for strValue in listActor if strValue != "system"
    )
    tupleModule = tuple(query.getlist("module"))
    tupleAction = tuple(query.getlist("action"))
    if any(re.fullmatch(r"[a-z_]{1,32}", strValue) is None for strValue in tupleModule):
        raise ValueError("Invalid audit module.")
    if any(
        len(strValue) > 64 or re.fullmatch(r"[a-z_]+\.[a-z_]+", strValue) is None
        for strValue in tupleAction
    ):
        raise ValueError("Invalid audit action.")
    try:
        tupleResult = tuple(AuditResult(strValue) for strValue in query.getlist("result"))
    except ValueError:
        raise ValueError("Invalid audit result.") from None
    return AuditListFilters(
        fromTime=fromTime,
        untilTime=untilTime,
        actorIds=tupleActorId,
        includeSystem="system" in listActor,
        modules=tupleModule,
        actions=tupleAction,
        results=tupleResult,
    )


def _build_record_payload(record: AuditRecord) -> dict[str, object]:
    return {
        "id": record.id,
        "created_at": record.created_at,
        "actor_id": record.actor_id,
        "actor_name": record.actor_name if record.actor_id is not None else "System",
        "channel": record.channel,
        "module": record.module,
        "action": record.action,
        "object_type": record.object_type,
        "object_id": record.object_id,
        "object_name": record.object_name,
        "result": record.result,
    }


def _build_details_payload(record: AuditRecord) -> dict[str, object]:
    def format_change_value(value: object) -> str:
        return (
            value
            if isinstance(value, str)
            else json.dumps(value, ensure_ascii=False, indent=2)
        )

    # The writer already allowlists metadata; project its saved values without another business-object scan.
    details = record.details
    listChange = [
        {
            "field": strField,
            "before": format_change_value(change["before"])
            if "before" in change
            else None,
            "after": format_change_value(change["after"]) if "after" in change else None,
        }
        for strField, change in details.get("changes", {}).items()
    ]
    listChange.extend(
        {"field": strField, "before": None, "after": None}
        for strField in details.get("changed_fields", [])
    )
    return {
        **_build_record_payload(record),
        "organization_id": record.organization_id,
        "organization_name": record.organization_name,
        "department_id": record.department_id,
        "request_id": record.request_id,
        "stage": details.get("stage", AuditStage.OPERATION),
        "reason_code": details.get("reason_code"),
        "http_status": details.get("http_status"),
        "changes": listChange,
        "details_omitted": details.get("details_omitted", False),
    }


def _build_audit_error_response(e: Exception) -> JsonResponse:
    if isinstance(e, PermissionDenied):
        return build_error_response(
            "audit_access_required",
            "Organization audit access is unavailable.",
            statusCode=403,
        )
    if isinstance(e, InvalidPage):
        return build_error_response(
            "audit_page_not_found", "Audit page not found.", statusCode=404
        )
    if isinstance(e, AuditRecord.DoesNotExist):
        return build_error_response(
            "audit_record_not_found",
            "The audit record is unavailable or has been removed by retention.",
            statusCode=404,
        )
    if isinstance(e, (ContractValidationError, PydanticSerializationError)):
        _LOGGER.exception("Could not build the organization audit response.")
        return build_error_response(
            "internal_server_error",
            "The service could not build a valid response.",
            statusCode=500,
        )
    return build_service_unavailable_response()


@never_cache
@require_GET
def list_organization_audit(request: HttpRequest) -> JsonResponse:
    """Return one page of the signed-in administrator's organization history."""
    try:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        user = cast(User, request.user)
        membership = get_current_membership(actorId=user.id)
        check_request_budget(request, membership.organization)
        # Only parsing failures belong to the client; query and response errors do not.
        try:
            filters = _parse_audit_filters(request.GET, user.time_zone)
            intPage = parse_page_number(request.GET)
        except ValidationError as e:
            return build_error_response(
                "invalid_audit_filters",
                "Some audit filters are invalid.",
                statusCode=400,
                fields=e.message_dict,
            )
        except ValueError:
            return build_error_response(
                "invalid_audit_filters",
                "Send valid audit filters and one positive page number.",
                statusCode=400,
            )
        auditPage = get_audit_list(
            actorId=user.id,
            organizationId=membership.organization_id,
            channel=AccessChannel.SESSION,
            filters=filters,
            pageNumber=intPage,
        )
        return JsonResponse(
            AuditListResponse.model_validate({
                "records": [
                    _build_record_payload(record) for record in auditPage.object_list
                ],
                "pagination": {
                    "page": auditPage.number,
                    "page_size": auditPage.paginator.per_page,
                    "total_count": auditPage.paginator.count,
                    "total_pages": auditPage.paginator.num_pages,
                },
            }).model_dump(mode="python")
        )
    except (
        PermissionDenied,
        InvalidPage,
        ContractValidationError,
        PydanticSerializationError,
        ImproperlyConfigured,
        DatabaseError,
    ) as e:
        return _build_audit_error_response(e)


@never_cache
@require_GET
def get_organization_audit_filters(request: HttpRequest) -> JsonResponse:
    """Return retained history's selectable actors, modules and actions."""
    try:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        user = cast(User, request.user)
        membership = get_current_membership(actorId=user.id)
        check_request_budget(request, membership.organization)
        options = get_audit_filter_options(
            actorId=user.id,
            organizationId=membership.organization_id,
            channel=AccessChannel.SESSION,
        )
        return JsonResponse(
            AuditFilterOptionsResponse.model_validate(options).model_dump(mode="python")
        )
    except (
        PermissionDenied,
        ContractValidationError,
        PydanticSerializationError,
        ImproperlyConfigured,
        DatabaseError,
    ) as e:
        return _build_audit_error_response(e)


@never_cache
@require_GET
def get_organization_audit_details(
    request: HttpRequest, auditId: uuid.UUID
) -> JsonResponse:
    """Read a single tenant record; a platform or foreign record is never selected."""
    try:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        user = cast(User, request.user)
        membership = get_current_membership(actorId=user.id)
        check_request_budget(request, membership.organization)
        record = get_audit_details(
            actorId=user.id,
            organizationId=membership.organization_id,
            channel=AccessChannel.SESSION,
            auditId=auditId,
        )
        return JsonResponse(
            AuditDetailsResponse.model_validate({
                "record": _build_details_payload(record)
            }).model_dump(mode="python")
        )
    except (
        PermissionDenied,
        AuditRecord.DoesNotExist,
        ContractValidationError,
        PydanticSerializationError,
        ImproperlyConfigured,
        DatabaseError,
    ) as e:
        return _build_audit_error_response(e)
