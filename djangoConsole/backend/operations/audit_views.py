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
from django.db.models import QuerySet
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
from organizations.limits import LIMIT_DEFINITIONS, LimitUnit
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
    get_current_membership,
    require_organization_business_available,
    require_organization_admin,
)
from organizations.rate_limits import check_request_budget

from .access import get_platform_actor
from .audit_queries import (
    AuditListFilters,
    get_audit_list,
    get_audit_filter_options,
)
from .contracts import (
    AuditAction,
    AuditResult,
    AuditStage,
    AuditListResponse,
    PlatformAuditListResponse,
    AuditFilterOptionsResponse,
    PlatformAuditFilterOptionsResponse,
    AuditDetailsResponse,
)
from .models import AuditScope, AuditRecord

_LOGGER = logging.getLogger("console.operations")


def _get_authorized_audit_query(
    request: HttpRequest, scope: AuditScope
) -> tuple[User, QuerySet[AuditRecord]]:
    if scope == AuditScope.PLATFORM:
        actor = get_platform_actor(request)
        return actor, AuditRecord.objects.filter(scope=AuditScope.PLATFORM)

    actor = cast(User, request.user)
    membership = get_current_membership(actorId=actor.pk)
    access = OrganizationAccessContext(
        actor=cast(User, membership.user),
        organization=membership.organization,
        isOrgAdmin=membership.is_org_admin,
        channel=AccessChannel.SESSION,
    )
    require_organization_business_available(access.organization)
    require_organization_admin(access)
    check_request_budget(request, access.organization)
    # An organization ID on a platform record never makes it tenant history.
    return access.actor, AuditRecord.objects.filter(
        scope=AuditScope.ORGANIZATION, organization_id=access.organization.pk
    )


def _parse_audit_filters(
    query: QueryDict, defaultTimeZone: str, scope: AuditScope
) -> AuditListFilters:
    setSingleField = {"page", "date_from", "date_to", "time_zone"}
    setMultipleField = {"actor_id", "action", "result"}
    setMultipleField.add("organization_id" if scope == AuditScope.PLATFORM else "module")
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
    listOrganization = query.getlist("organization_id")
    tupleOrganizationId = tuple(
        uuid.UUID(strValue) for strValue in listOrganization if strValue != "instance"
    )
    tupleModule = tuple(query.getlist("module"))
    if any(re.fullmatch(r"[a-z_]{1,32}", strValue) is None for strValue in tupleModule):
        raise ValueError("Invalid audit module.")
    try:
        tupleAction = tuple(AuditAction(strValue) for strValue in query.getlist("action"))
    except ValueError:
        raise ValueError("Invalid audit action.") from None
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
        organizationIds=tupleOrganizationId,
        includeInstance="instance" in listOrganization,
    )


def _build_record_payload(record: AuditRecord) -> dict[str, object]:
    dictRecord: dict[str, object] = {
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
    if record.scope == AuditScope.PLATFORM:
        dictRecord.update({
            "organization_id": record.organization_id,
            "organization_name": record.organization_name,
        })
    return dictRecord


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
    if record.action == AuditAction.ORGANIZATION_UPDATE_LIMITS:
        # Read the saved limits and sources, never today's defaults or organization state.
        metadata = details.get("metadata", {})
        dictLimit = metadata.get("limits", {})
        for definition in LIMIT_DEFINITIONS:
            if definition.configName not in dictLimit:
                continue
            dictValues = dict(
                zip(metadata["columns"], dictLimit[definition.configName], strict=True)
            )
            strUnit = (
                " bytes"
                if definition.unit == LimitUnit.BYTES
                else "/min"
                if definition.unit == LimitUnit.PER_MINUTE
                else ""
            )
            dictChange = {"field": definition.label}
            for strSide in ("before", "after"):
                strSource = (
                    "Default" if dictValues[f"{strSide}_override"] is None else "Override"
                )
                dictChange[strSide] = (
                    f"{dictValues[f'{strSide}_limit']:,}{strUnit} ({strSource})"
                )
            listChange.append(dictChange)
    return {
        **_build_record_payload(record),
        "organization_id": record.organization_id,
        "organization_name": record.organization_name,
        "department_id": record.department_id,
        "request_id": record.request_id,
        "stage": details.get("stage", AuditStage.OPERATION),
        "reason": details.get("metadata", {}).get("reason")
        if record.scope == AuditScope.PLATFORM
        and record.action
        in (AuditAction.ORGANIZATION_SUSPEND, AuditAction.ORGANIZATION_RESUME)
        else None,
        "reason_code": details.get("reason_code"),
        "http_status": details.get("http_status"),
        "changes": listChange,
        "details_omitted": details.get("details_omitted", False),
    }


def _build_audit_error_response(e: Exception, scope: AuditScope) -> JsonResponse:
    if isinstance(e, PermissionDenied):
        return build_error_response(
            "platform_access_required"
            if scope == AuditScope.PLATFORM
            else "audit_access_required",
            "Platform administrator access is required."
            if scope == AuditScope.PLATFORM
            else "Organization audit access is unavailable.",
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
        _LOGGER.exception("Could not build the audit response.")
        return build_error_response(
            "internal_server_error",
            "The service could not build a valid response.",
            statusCode=500,
        )
    return build_service_unavailable_response()


@never_cache
@require_GET
def list_audit(
    request: HttpRequest, *, scope: AuditScope = AuditScope.ORGANIZATION
) -> JsonResponse:
    """Return one page of authorized history; the URL determines its scope."""
    try:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        actor, auditQuery = _get_authorized_audit_query(request, scope)
        # Only parsing failures belong to the client; query and response errors do not.
        try:
            filters = _parse_audit_filters(request.GET, actor.time_zone, scope)
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
            auditQuery=auditQuery,
            filters=filters,
            pageNumber=intPage,
        )
        responseType = (
            PlatformAuditListResponse
            if scope == AuditScope.PLATFORM
            else AuditListResponse
        )
        return JsonResponse(
            responseType.model_validate({
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
        return _build_audit_error_response(e, scope)


@never_cache
@require_GET
def get_audit_filters(
    request: HttpRequest, *, scope: AuditScope = AuditScope.ORGANIZATION
) -> JsonResponse:
    """Return selectable values from retained history in the authorized scope."""
    try:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        _, auditQuery = _get_authorized_audit_query(request, scope)
        if request.GET:
            try:
                if (
                    scope != AuditScope.PLATFORM
                    or set(request.GET) != {"organization_id"}
                    or len(request.GET.getlist("organization_id")) != 1
                ):
                    raise ValueError
                organizationId = uuid.UUID(request.GET["organization_id"])
            except ValueError:
                return build_error_response(
                    "invalid_audit_filters",
                    "Send one valid organization ID or no query parameters.",
                    statusCode=400,
                )
            auditQuery = auditQuery.filter(organization_id=organizationId)
        options = get_audit_filter_options(
            auditQuery=auditQuery, platform=scope == AuditScope.PLATFORM
        )
        responseType = (
            PlatformAuditFilterOptionsResponse
            if scope == AuditScope.PLATFORM
            else AuditFilterOptionsResponse
        )
        return JsonResponse(
            responseType.model_validate(options).model_dump(mode="python")
        )
    except (
        PermissionDenied,
        ContractValidationError,
        PydanticSerializationError,
        ImproperlyConfigured,
        DatabaseError,
    ) as e:
        return _build_audit_error_response(e, scope)


@never_cache
@require_GET
def get_audit_details(
    request: HttpRequest,
    auditId: uuid.UUID,
    *,
    scope: AuditScope = AuditScope.ORGANIZATION,
) -> JsonResponse:
    """Read one saved snapshot without querying its current business object."""
    try:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        _, auditQuery = _get_authorized_audit_query(request, scope)
        if request.GET:
            return build_error_response(
                "invalid_audit_filters",
                "This request does not accept query parameters.",
                statusCode=400,
            )
        record = auditQuery.get(pk=auditId)
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
        return _build_audit_error_response(e, scope)
