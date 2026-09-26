# FileName: member_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from collections.abc import Mapping
from typing import cast

from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.core.paginator import InvalidPage
from django.db import DatabaseError
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from accounts.models import User
from console_project.http import (
    build_error_response,
    build_service_unavailable_response,
    parse_json_request,
    parse_page_number,
)

from .contracts import MemberListResponse, MemberDetailsResponse
from .http import MembershipUpdateRequest
from .member_queries import MemberInfo, get_member_details, get_member_list
from .models import DepartmentRole, Membership
from .permissions import AccessChannel, get_current_membership
from .member_services import update_membership

_INT_MAX_MEMBERSHIP_BODY_BYTES = 64 * 1024


def _build_member_payload(memberInfo: MemberInfo) -> dict[str, object]:
    return {
        "user": {
            "id": memberInfo.userId,
            "email": memberInfo.email,
            "username": memberInfo.username,
        },
        "is_org_admin": memberInfo.isOrgAdmin,
        "department_roles": [
            {
                "department": {
                    "id": roleInfo.departmentId,
                    "name": roleInfo.departmentName,
                    "path": roleInfo.departmentPath,
                },
                "role": roleInfo.role,
            }
            for roleInfo in memberInfo.departmentRoles
        ],
        "notes": memberInfo.notes,
        "joined_at": memberInfo.joinedAt,
    }


def _build_saved_member_response(
    membership: Membership, departmentRoles: Mapping[uuid.UUID, DepartmentRole]
) -> JsonResponse:
    # NOTE: Self-demotion can remove read access, so do not query again after saving.
    return JsonResponse({
        "member": {
            "user_id": membership.user_id,
            "is_org_admin": membership.is_org_admin,
            "department_roles": [
                {"department_id": departmentId, "role": role}
                for departmentId, role in departmentRoles.items()
            ],
            "notes": membership.notes,
        }
    })


def _build_membership_validation_response(
    validationError: ValidationError,
) -> JsonResponse:
    if hasattr(validationError, "error_dict"):
        dictFieldMessage = validationError.message_dict
        boolLastAdmin = any(
            fieldError.code == "last_org_admin"
            for listFieldError in validationError.error_dict.values()
            for fieldError in listFieldError
        )
    else:
        dictFieldMessage = {"__all__": validationError.messages}
        boolLastAdmin = False
    return build_error_response(
        "last_org_admin" if boolLastAdmin else "invalid_membership",
        "The organization must retain at least one active administrator."
        if boolLastAdmin
        else "Some membership fields are invalid.",
        statusCode=409 if boolLastAdmin else 400,
        fields=dictFieldMessage,
    )


def _get_page_number(request: HttpRequest) -> int | JsonResponse:
    try:
        return parse_page_number(request.GET)
    except ValueError:
        return build_error_response(
            "invalid_page", "Send one positive integer page number.", statusCode=400
        )


@never_cache
@require_GET
def list_members(request: HttpRequest) -> JsonResponse:
    """Read a page of members in the signed-in administrator's organization."""
    try:
        if not request.user.is_authenticated:
            return build_error_response(
                "authentication_required", "Sign in to continue.", statusCode=401
            )
        user = cast(User, request.user)
        membership = get_current_membership(actorId=user.id)
        intPageNumber = _get_page_number(request)
        if isinstance(intPageNumber, JsonResponse):
            return intPageNumber
        memberPage = get_member_list(
            actorId=user.id,
            organizationId=membership.organization_id,
            channel=AccessChannel.SESSION,
            pageNumber=intPageNumber,
        )
        return JsonResponse(
            MemberListResponse.model_validate({
                "members": [
                    _build_member_payload(memberInfo) for memberInfo in memberPage.members
                ],
                "pagination": {
                    "page": memberPage.page,
                    "page_size": memberPage.pageSize,
                    "total_count": memberPage.totalCount,
                    "total_pages": memberPage.totalPages,
                },
            }).model_dump(mode="python")
        )
    except InvalidPage:
        return build_error_response(
            "member_page_not_found", "Member page not found.", statusCode=404
        )
    except PermissionDenied:
        return build_error_response(
            "member_access_required",
            "Member administration is unavailable.",
            statusCode=403,
        )
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()


@never_cache
@require_http_methods(["GET", "POST"])
def get_or_update_member(request: HttpRequest, userId: uuid.UUID) -> JsonResponse:
    """Read member details or save organization and department roles with Notes."""
    try:
        if not request.user.is_authenticated:
            return build_error_response(
                "authentication_required", "Sign in to continue.", statusCode=401
            )
        user = cast(User, request.user)
        currentMembership = get_current_membership(actorId=user.id)
        if request.method == "POST":
            membershipRequest = parse_json_request(
                request,
                MembershipUpdateRequest,
                maxBodyBytes=_INT_MAX_MEMBERSHIP_BODY_BYTES,
            )
            if isinstance(membershipRequest, JsonResponse):
                return membershipRequest
            dictDepartmentRole = {
                roleRequest.department_id: roleRequest.role
                for roleRequest in membershipRequest.department_roles
            }
            membership = update_membership(
                actorId=user.id,
                organizationId=currentMembership.organization_id,
                channel=AccessChannel.SESSION,
                userId=userId,
                isOrgAdmin=membershipRequest.is_org_admin,
                departmentRoles=dictDepartmentRole,
                notes=membershipRequest.notes,
            )
            return _build_saved_member_response(membership, dictDepartmentRole)

        memberInfo = get_member_details(
            actorId=user.id,
            organizationId=currentMembership.organization_id,
            channel=AccessChannel.SESSION,
            userId=userId,
        )
        # API key metadata is loaded separately through the member's api-keys endpoint.
        return JsonResponse(
            MemberDetailsResponse.model_validate({
                "member": _build_member_payload(memberInfo)
            }).model_dump(mode="python")
        )
    except ValidationError as e:
        return _build_membership_validation_response(e)
    except Membership.DoesNotExist:
        return build_error_response(
            "member_not_found", "Member not found or unavailable.", statusCode=404
        )
    except PermissionDenied:
        return build_error_response(
            "member_access_required",
            "Member administration is unavailable.",
            statusCode=403,
        )
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()
