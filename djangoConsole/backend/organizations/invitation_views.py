# FileName: invitation_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from collections.abc import Callable
from datetime import timedelta
from functools import wraps
from typing import cast

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.core.paginator import InvalidPage, Paginator
from django.db import DatabaseError
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_variables
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from accounts.models import User
from accounts.rate_limits import (
    reserve_invitation_email_request,
    reserve_registration_token_request,
)
from console_project.config import LimitsConfig
from console_project.http import (
    JsonRequest,
    build_error_response,
    build_service_unavailable_response,
    build_rate_limited_response,
    parse_json_request,
    parse_page_number,
)
from notifications.models import EmailDelivery

from .invitations import (
    InvitationConflictError,
    InvitationCooldownError,
    complete_invitation_registration,
    create_member_invitation,
    get_invitation_registration_info,
    get_invitation_status,
    resend_member_invitation,
    revoke_member_invitation,
)
from .contracts import (
    InvitationCreateRequest,
    InvitationTokenRequest,
    InvitationCompletionRequest,
    InvitationRegistrationResponse,
    InvitationDetailsResponse,
    InvitationListResponse,
)
from .department_queries import get_department_path
from .models import Department, DepartmentRole, InvitationDepartmentRole, MemberInvitation
from .permissions import (
    AccessChannel,
    get_current_membership,
    require_organization_admin,
    resolve_organization_access,
)

_INT_MAX_INVITATION_BODY_BYTES = 64 * 1024
_INT_INVITATIONS_PER_PAGE = 50


def _handle_invitation_errors[**Params](
    view: Callable[Params, JsonResponse],
) -> Callable[Params, JsonResponse]:
    @wraps(view)
    def wrapped(*args: Params.args, **kwargs: Params.kwargs) -> JsonResponse:
        try:
            return view(*args, **kwargs)
        except InvitationCooldownError as e:
            return build_rate_limited_response(e.retryAfterSeconds)
        except InvitationConflictError as e:
            return build_error_response(e.errorCode, str(e), statusCode=409)
        except ValidationError as e:
            if hasattr(e, "error_dict"):
                return build_error_response(
                    "invalid_invitation",
                    "Some invitation fields are invalid.",
                    statusCode=400,
                    fields=e.message_dict,
                )
            strErrorCode = e.error_list[0].code or "invalid_invitation"
            return build_error_response(
                strErrorCode, " ".join(e.messages), statusCode=400
            )
        except (MemberInvitation.DoesNotExist, InvalidPage):
            return build_error_response(
                "invitation_not_found",
                "Invitation not found or unavailable.",
                statusCode=404,
            )
        except PermissionDenied:
            return build_error_response(
                "invitation_access_required",
                "This invitation operation is unavailable.",
                statusCode=403,
            )
        except (ImproperlyConfigured, DatabaseError):
            return build_service_unavailable_response()

    return wrapped


def _get_invitation_actor(request: HttpRequest) -> tuple[User, uuid.UUID] | JsonResponse:
    if not request.user.is_authenticated:
        return build_error_response(
            "authentication_required", "Sign in to continue.", statusCode=401
        )
    user = cast(User, request.user)
    membership = get_current_membership(actorId=user.id)
    access = resolve_organization_access(
        actorId=user.id,
        organizationId=membership.organization_id,
        channel=AccessChannel.SESSION,
    )
    require_organization_admin(access)
    return user, membership.organization_id


def _build_invitation_payloads(
    invitations: list[MemberInvitation],
) -> list[dict[str, object]]:
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    dictDepartmentById = (
        Department.objects
        .filter(
            organization_id__in={invitation.organization_id for invitation in invitations}
        )
        .only("id", "name", "parent")
        .in_bulk()
    )
    dictRoleByInvitationId: dict[uuid.UUID, list[InvitationDepartmentRole]] = {
        invitation.id: [] for invitation in invitations
    }
    for proposedRole in (
        InvitationDepartmentRole.objects
        .filter(invitation_id__in=dictRoleByInvitationId)
        .select_related("department")
        .order_by("department__name", "department_id")
    ):
        dictRoleByInvitationId[proposedRole.invitation_id].append(proposedRole)
    dictDeliveryByRequestId = {
        delivery.invitation_request_id: delivery
        for delivery in EmailDelivery.objects.filter(
            invitation_id__in=[invitation.id for invitation in invitations],
            invitation_request_id__in=[
                invitation.request_id for invitation in invitations
            ],
        ).order_by("created_at", "id")
    }
    listInvitationPayload: list[dict[str, object]] = []
    for invitation in invitations:
        delivery = dictDeliveryByRequestId.get(invitation.request_id)
        listInvitationPayload.append({
            "id": invitation.id,
            "email": invitation.email,
            "is_org_admin": invitation.is_org_admin,
            "department_roles": [
                {
                    "department_id": proposedRole.department_id,
                    "department_name": proposedRole.department.name,
                    "department_path": get_department_path(
                        proposedRole.department, dictDepartmentById
                    ),
                    "department_deleted": proposedRole.department.deleted_at is not None,
                    "role": proposedRole.role,
                }
                for proposedRole in dictRoleByInvitationId[invitation.id]
            ],
            "notes": invitation.notes,
            "status": get_invitation_status(invitation),
            "created_at": invitation.created_at,
            "requested_at": invitation.requested_at,
            "expires_at": invitation.expires_at,
            "resend_available_at": invitation.requested_at
            + timedelta(seconds=limits.emailResendSeconds),
            "accepted_at": invitation.accepted_at,
            "revoked_at": invitation.revoked_at,
            "email_delivery": None
            if delivery is None
            else {
                "id": delivery.id,
                "status": delivery.status,
                "reason_code": delivery.reason_code,
                "attempted_at": delivery.attempted_at,
                "finished_at": delivery.finished_at,
            },
        })
    return listInvitationPayload


def _build_invitation_response(
    invitation: MemberInvitation, *, statusCode: int = 200
) -> JsonResponse:
    return JsonResponse(
        InvitationDetailsResponse.model_validate({
            "invitation": _build_invitation_payloads([invitation])[0]
        }).model_dump(mode="python"),
        status=statusCode,
    )


@never_cache
@require_http_methods(["GET", "POST"])
@_handle_invitation_errors
def list_or_create_invitations(request: HttpRequest) -> JsonResponse:
    actorInfo = _get_invitation_actor(request)
    if isinstance(actorInfo, JsonResponse):
        return actorInfo
    user, organizationId = actorInfo
    if request.method == "POST":
        invitationRequest = parse_json_request(
            request, InvitationCreateRequest, maxBodyBytes=_INT_MAX_INVITATION_BODY_BYTES
        )
        if isinstance(invitationRequest, JsonResponse):
            return invitationRequest
        intRetryAfterSeconds = reserve_invitation_email_request(
            request.META.get("REMOTE_ADDR", ""), actorId=str(user.id)
        )
        if intRetryAfterSeconds:
            return build_rate_limited_response(intRetryAfterSeconds)
        invitation = create_member_invitation(
            actorId=user.id,
            organizationId=organizationId,
            channel=AccessChannel.SESSION,
            email=invitationRequest.email,
            isOrgAdmin=invitationRequest.is_org_admin,
            departmentRoles={
                roleRequest.department_id: DepartmentRole(roleRequest.role)
                for roleRequest in invitationRequest.department_roles
            },
            notes=invitationRequest.notes,
        )
        return _build_invitation_response(invitation, statusCode=201)
    try:
        intPageNumber = parse_page_number(request.GET)
    except ValueError:
        return build_error_response(
            "invalid_page", "Send one positive integer page number.", statusCode=400
        )
    # NOTE: Accepted and revoked records remain addressable but leave the open invitation list.
    invitationQuery = MemberInvitation.objects.filter(
        organization_id=organizationId,
        accepted_at__isnull=True,
        revoked_at__isnull=True,
    ).order_by("-created_at", "-id")
    paginator = Paginator(invitationQuery, _INT_INVITATIONS_PER_PAGE)
    invitationPage = paginator.page(intPageNumber)
    return JsonResponse(
        InvitationListResponse.model_validate({
            "invitations": _build_invitation_payloads(list(invitationPage.object_list)),
            "pagination": {
                "page": invitationPage.number,
                "page_size": _INT_INVITATIONS_PER_PAGE,
                "total_count": paginator.count,
                "total_pages": paginator.num_pages,
            },
        }).model_dump(mode="python")
    )


@never_cache
@require_GET
@_handle_invitation_errors
def get_invitation_details(request: HttpRequest, invitationId: uuid.UUID) -> JsonResponse:
    actorInfo = _get_invitation_actor(request)
    if isinstance(actorInfo, JsonResponse):
        return actorInfo
    _, organizationId = actorInfo
    invitation = MemberInvitation.objects.get(
        pk=invitationId, organization_id=organizationId
    )
    return _build_invitation_response(invitation)


@never_cache
@require_POST
@_handle_invitation_errors
def resend_or_revoke_invitation(
    request: HttpRequest, invitationId: uuid.UUID, *, resend: bool
) -> JsonResponse:
    actorInfo = _get_invitation_actor(request)
    if isinstance(actorInfo, JsonResponse):
        return actorInfo
    user, organizationId = actorInfo
    emptyRequest = parse_json_request(request, JsonRequest)
    if isinstance(emptyRequest, JsonResponse):
        return emptyRequest
    if resend:
        intRetryAfterSeconds = reserve_invitation_email_request(
            request.META.get("REMOTE_ADDR", ""), actorId=str(user.id)
        )
        if intRetryAfterSeconds:
            return build_rate_limited_response(intRetryAfterSeconds)
    operation = resend_member_invitation if resend else revoke_member_invitation
    invitation = operation(
        actorId=user.id,
        organizationId=organizationId,
        channel=AccessChannel.SESSION,
        invitationId=invitationId,
    )
    return _build_invitation_response(invitation)


@never_cache
@require_POST
@_handle_invitation_errors
@sensitive_variables()
def check_invitation_link(request: HttpRequest) -> JsonResponse:
    invitationRequest = parse_json_request(request, InvitationTokenRequest)
    if isinstance(invitationRequest, JsonResponse):
        return invitationRequest
    strToken = invitationRequest.token.get_secret_value()
    # Both public registration paths share the source and proof request budgets.
    intRetryAfterSeconds = reserve_registration_token_request(
        request.META.get("REMOTE_ADDR", ""), token=strToken
    )
    if intRetryAfterSeconds:
        return build_rate_limited_response(intRetryAfterSeconds)
    strEmail, strOrganizationName = get_invitation_registration_info(strToken)
    return JsonResponse(
        InvitationRegistrationResponse(
            email=strEmail, organization_name=strOrganizationName
        ).model_dump(mode="python")
    )


@never_cache
@require_POST
@_handle_invitation_errors
@sensitive_variables()
def complete_invited_registration(request: HttpRequest) -> JsonResponse:
    invitationRequest = parse_json_request(request, InvitationCompletionRequest)
    if isinstance(invitationRequest, JsonResponse):
        return invitationRequest
    strToken = invitationRequest.token.get_secret_value()
    intRetryAfterSeconds = reserve_registration_token_request(
        request.META.get("REMOTE_ADDR", ""), token=strToken
    )
    if intRetryAfterSeconds:
        return build_rate_limited_response(intRetryAfterSeconds)
    complete_invitation_registration(
        token=strToken,
        password=invitationRequest.password.get_secret_value(),
        username=invitationRequest.username,
    )
    return JsonResponse({"message": "Account created. Sign in to continue."}, status=201)
