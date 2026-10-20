# FileName: organization_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.core.paginator import InvalidPage, Paginator
from django.db import DatabaseError, transaction
from django.db.models import Prefetch, Q
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from pydantic import ValidationError as ContractValidationError

from accounts.session_revocation import SessionInvalidatedError
from console_project.constants import INT_LIST_PAGE_SIZE
from console_project.contracts import MessageResponse, PaginationResponse
from console_project.http import (
    build_error_response,
    build_authentication_required_response,
    build_service_unavailable_response,
    parse_json_request,
    parse_page_number,
)
from organizations.models import Organization, Membership
from organizations.limits import validate_limit_overrides, get_organization_limits
from organizations.limit_emails import queue_organization_limits_notices
from organizations.usage import get_limits_version, get_organization_usage

from .access import get_platform_actor
from .audit import record_audit
from .contracts import (
    PlatformOrganizationStatus,
    PlatformOrganizationFilters,
    PlatformAdministratorResponse,
    PlatformOrganizationResponse,
    PlatformOrganizationListResponse,
    OrganizationLimitsRequest,
)
from .models import AuditScope


@never_cache
@require_GET
def list_platform_organizations(request: HttpRequest) -> JsonResponse:
    """List organization operating metadata without granting access to tenant resources."""
    try:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        get_platform_actor(request)
        query = request.GET
        if set(query) - {"page", "name", "organization_id", "status"} or any(
            len(query.getlist(key)) > 1 for key in ("page", "name", "organization_id")
        ):
            raise ValueError("Invalid organization filters.")
        filters = PlatformOrganizationFilters(
            page=parse_page_number(query),
            name=query.get("name", "").strip(),
            organization_id=uuid.UUID(query["organization_id"])
            if query.get("organization_id")
            else None,
            status=[
                PlatformOrganizationStatus(value) for value in query.getlist("status")
            ],
        )
        organizations = Organization.objects.filter(name__icontains=filters.name)
        if filters.organization_id is not None:
            organizations = organizations.filter(pk=filters.organization_id)
        if filters.status:
            conditions = Q()
            for status in filters.status:
                match status:
                    case PlatformOrganizationStatus.ACTIVE:
                        conditions |= Q(
                            suspended_at__isnull=True, deletion_requested_at__isnull=True
                        )
                    case PlatformOrganizationStatus.SUSPENDED:
                        conditions |= Q(suspended_at__isnull=False)
                    case PlatformOrganizationStatus.DELETION_SCHEDULED:
                        conditions |= Q(
                            deletion_requested_at__isnull=False,
                            deletion_started_at__isnull=True,
                        )
                    case PlatformOrganizationStatus.DELETION_IN_PROGRESS:
                        conditions |= Q(deletion_started_at__isnull=False)
            organizations = organizations.filter(conditions)
        page = Paginator(
            organizations.order_by("name", "id").prefetch_related(
                Prefetch(
                    "memberships",
                    queryset=Membership.objects
                    .filter(is_org_admin=True, user__is_active=True)
                    .select_related("user")
                    .order_by("user_id"),
                )
            ),
            INT_LIST_PAGE_SIZE,
        ).page(filters.page)
        response = PlatformOrganizationListResponse(
            organizations=[
                PlatformOrganizationResponse(
                    id=organization.pk,
                    name=organization.name,
                    notes=organization.notes,
                    created_at=organization.created_at,
                    administrators=[
                        PlatformAdministratorResponse(
                            id=membership.user_id,
                            name=membership.user.username,
                            email=membership.user.email,
                        )
                        for membership in organization.memberships.all()
                    ],
                    suspended_at=organization.suspended_at,
                    deletion_requested_at=organization.deletion_requested_at,
                    deletion_started_at=organization.deletion_started_at,
                )
                for organization in page
            ],
            pagination=PaginationResponse(
                page=page.number,
                page_size=INT_LIST_PAGE_SIZE,
                total_count=page.paginator.count,
                total_pages=page.paginator.num_pages,
            ),
        )
        return JsonResponse(response.model_dump(mode="python"))
    except PermissionDenied:
        return build_error_response(
            "platform_access_required",
            "Platform administrator access is required.",
            statusCode=403,
        )
    except (ValueError, ContractValidationError, InvalidPage):
        return build_error_response(
            "invalid_filters",
            "Select valid organization filters and a valid page.",
            statusCode=400,
        )
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()


@never_cache
@require_http_methods(["GET", "POST"])
def get_or_update_organization_limits(
    request: HttpRequest, organizationId: uuid.UUID
) -> JsonResponse:
    """Edit only explicitly allowed quotas; resetting removes overrides, never usage."""
    try:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        get_platform_actor(request)
        if request.method == "POST":
            payload = parse_json_request(request, OrganizationLimitsRequest)
            if isinstance(payload, JsonResponse):
                return payload
            dictOverride = validate_limit_overrides(payload.overrides)
            with transaction.atomic():
                organization = Organization.objects.select_for_update().get(
                    pk=organizationId
                )
                actor = get_platform_actor(request, forUpdate=True)
                if organization.deletion_started_at is not None:
                    return build_error_response(
                        "organization_deleting",
                        "Organization deletion is already in progress.",
                        statusCode=409,
                    )
                if payload.version != get_limits_version(organization):
                    return build_error_response(
                        "limits_changed",
                        "Limits or defaults have changed. Refresh and review them before saving.",
                        statusCode=409,
                    )
                previous = get_organization_limits(organization)
                dictPreviousOverride = organization.limit_overrides
                if dictPreviousOverride != dictOverride:
                    organization.limit_overrides = dictOverride
                    current = get_organization_limits(organization)
                    dictChange = {
                        key: {
                            "before": dictPreviousOverride.get(key),
                            "after": dictOverride.get(key),
                            "before_limit": getattr(previous, key),
                            "after_limit": getattr(current, key),
                        }
                        for key in sorted(
                            dictPreviousOverride.keys() | dictOverride.keys()
                        )
                        if dictPreviousOverride.get(key) != dictOverride.get(key)
                    }
                    organization.save(update_fields=["limit_overrides"])
                    # Compact named columns retain all values/sources within the audit's 4 KiB limit.
                    # A null override means Default; an integer means Override, including zero.
                    record_audit(
                        "organization.update_limits",
                        actor=actor,
                        organization=organization,
                        target=organization,
                        scope=AuditScope.PLATFORM,
                        metadata={
                            "columns": [
                                "before_override",
                                "after_override",
                                "before_limit",
                                "after_limit",
                            ],
                            "limits": {
                                key: list(change.values())
                                for key, change in dictChange.items()
                            },
                        },
                    )
                    queue_organization_limits_notices(organization, dictChange)
            return JsonResponse(
                MessageResponse(message="Organization limits saved.").model_dump(
                    mode="python"
                )
            )
        else:
            organization = Organization.objects.get(pk=organizationId)
        # Usage and proxy activity are read after commit; no file/network operation holds the lock.
        return JsonResponse(
            get_organization_usage(organization).model_dump(mode="python")
        )
    except SessionInvalidatedError:
        return build_authentication_required_response(
            "The current session is no longer valid. Sign in again."
        )
    except PermissionDenied:
        return build_error_response(
            "platform_access_required",
            "Platform administrator access is required.",
            statusCode=403,
        )
    except Organization.DoesNotExist:
        return build_error_response(
            "organization_not_found",
            "This organization is no longer available.",
            statusCode=404,
        )
    except ValidationError as error:
        return build_error_response(
            "invalid_limits",
            " ".join(error.messages),
            statusCode=400,
            fields={"overrides": error.messages},
        )
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()
