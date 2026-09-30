# FileName: lifecycle_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from typing import cast

from django.contrib.auth import HASH_SESSION_KEY
from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_http_methods, require_POST
from pydantic import SecretStr

from accounts.models import User
from accounts.rate_limits import apply_organization_deletion_rate_limit
from accounts.session_revocation import SessionInvalidatedError
from console_project.contracts import JsonRequest
from console_project.http import (
    build_error_response,
    build_authentication_required_response,
    build_service_unavailable_response,
    build_rate_limited_response,
    parse_json_request,
)

from .lifecycle import cancel_organization_deletion, schedule_organization_deletion
from .models import Organization
from .permissions import (
    AccessChannel,
    is_organization_business_available,
    get_current_membership,
)


class OrganizationDeletionRequest(JsonRequest):
    current_password: SecretStr


def _build_organization_deletion_response(
    organization: Organization, *, isOrgAdmin: bool
) -> JsonResponse:
    boolBusinessAvailable = is_organization_business_available(organization)
    return JsonResponse({
        "organization": {
            "id": organization.id,
            "name": organization.name,
            "suspended_at": organization.suspended_at,
            "deletion_requested_at": organization.deletion_requested_at,
            "deletion_due_at": organization.deletion_due_at,
            "deletion_started_at": organization.deletion_started_at,
        },
        "is_org_admin": isOrgAdmin,
        "business_available": boolBusinessAvailable,
        "can_schedule_deletion": isOrgAdmin and boolBusinessAvailable,
        "can_cancel_deletion": (
            isOrgAdmin
            and organization.deletion_requested_at is not None
            and organization.deletion_started_at is None
        ),
    })


def _build_deletion_validation_response(validationError: ValidationError) -> JsonResponse:
    if hasattr(validationError, "error_dict"):
        return build_error_response(
            "invalid_organization_deletion",
            "The current password is incorrect.",
            statusCode=400,
            fields=validationError.message_dict,
        )
    strErrorCode = validationError.error_list[0].code or "invalid_organization_deletion"
    boolConflict = strErrorCode in {
        "deletion_already_scheduled",
        "deletion_not_scheduled",
        "deletion_in_progress",
    }
    return build_error_response(
        strErrorCode,
        " ".join(validationError.messages),
        statusCode=409 if boolConflict else 400,
    )


@sensitive_variables()
def _handle_organization_deletion(
    request: HttpRequest, *, cancelDeletion: bool
) -> JsonResponse:
    try:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        user = cast(User, request.user)
        membership = get_current_membership(actorId=user.id)
        if request.method == "GET":
            return _build_organization_deletion_response(
                membership.organization, isOrgAdmin=membership.is_org_admin
            )
        if not membership.is_org_admin:
            raise PermissionDenied("Organization administrator access is required.")

        # Neither endpoint accepts a caller-selected organization or account.
        deletionRequest = None
        if cancelDeletion:
            cancelRequest = parse_json_request(request, JsonRequest)
            if isinstance(cancelRequest, JsonResponse):
                return cancelRequest
        else:
            deletionRequest = parse_json_request(request, OrganizationDeletionRequest)
            if isinstance(deletionRequest, JsonResponse):
                return deletionRequest
            intRetryAfterSeconds = apply_organization_deletion_rate_limit(
                request.META.get("REMOTE_ADDR", ""), actorId=str(user.id)
            )
            if intRetryAfterSeconds:
                return build_rate_limited_response(intRetryAfterSeconds)

        strSessionAuthHash = cast(str, request.session.get(HASH_SESSION_KEY, ""))
        with transaction.atomic():
            if deletionRequest is None:
                organization = cancel_organization_deletion(
                    actorId=user.id,
                    organizationId=membership.organization_id,
                    channel=AccessChannel.SESSION,
                    sessionAuthHash=strSessionAuthHash,
                )
            else:
                organization = schedule_organization_deletion(
                    actorId=user.id,
                    organizationId=membership.organization_id,
                    channel=AccessChannel.SESSION,
                    currentPassword=deletionRequest.current_password.get_secret_value(),
                    sessionAuthHash=strSessionAuthHash,
                )
            if request.session.get_expiry_date() <= timezone.now():
                raise SessionInvalidatedError("The current session has expired.")
        return _build_organization_deletion_response(organization, isOrgAdmin=True)
    except SessionInvalidatedError:
        return build_authentication_required_response(
            "The current session is no longer valid. Sign in again."
        )
    except ValidationError as e:
        return _build_deletion_validation_response(e)
    except PermissionDenied:
        return build_error_response(
            "organization_deletion_unavailable",
            "Organization deletion is unavailable for this account or organization.",
            statusCode=403,
        )
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()


@never_cache
@require_http_methods(["GET", "POST"])
@sensitive_post_parameters()
@sensitive_variables()
def get_or_schedule_organization_deletion(request: HttpRequest) -> JsonResponse:
    """Show the current organization's deletion state or schedule deletion as an administrator."""
    return _handle_organization_deletion(request, cancelDeletion=False)


@never_cache
@require_POST
@sensitive_post_parameters()
@sensitive_variables()
def cancel_scheduled_organization_deletion(request: HttpRequest) -> JsonResponse:
    """Cancel through a current administrator's session without another password check."""
    return _handle_organization_deletion(request, cancelDeletion=True)
