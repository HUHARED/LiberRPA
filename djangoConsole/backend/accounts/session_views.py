# FileName: session_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import timedelta
from typing import cast

from django.conf import settings
from django.contrib.auth import HASH_SESSION_KEY, authenticate, login, logout
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.base import UpdateError
from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.http import HttpRequest, JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_GET, require_POST

from console_project.contracts import MessageResponse
from console_project.http import (
    build_error_response,
    build_authentication_required_response,
    build_service_unavailable_response,
    build_rate_limited_response,
    parse_json_request,
)
from operations.audit import record_audit
from organizations.models import Organization, Membership
from organizations.access import get_account_access_info
from organizations.http import build_account_access_payload
from organizations.permissions import AccessChannel

from .contracts import (
    LoginRequest,
    SessionUserResponse,
    SessionResponse,
    SessionRevocationRequest,
)
from .models import User, UserManager
from .rate_limits import apply_login_rate_limit, apply_session_revocation_rate_limit
from .session_revocation import SessionInvalidatedError, revoke_other_sessions

_REMEMBERED_SESSION_LIFETIME = timedelta(days=14)


def _build_session_response(request: HttpRequest, user: User) -> JsonResponse:
    # Return current identity only; business operations resolve their own current permissions.
    sessionResponse = SessionResponse(
        user=SessionUserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            time_zone=user.time_zone,
        ),
        expires_at=request.session.get_expiry_date(),
        csrf_token=get_token(request),
    )
    # Keep Django's existing UUID and datetime encoding, including its timestamp precision.
    return JsonResponse(sessionResponse.model_dump(mode="python"))


def _lock_session_audit_organization(user: User) -> Organization | None:
    """Serialize session auditing with organization cleanup without granting business access."""
    organizationId = (
        Membership.objects
        .filter(user_id=user.pk)
        .values_list("organization_id", flat=True)
        .first()
    )
    if organizationId is None:
        return None
    return Organization.objects.select_for_update().filter(pk=organizationId).first()


@never_cache
@require_POST
@sensitive_variables()
def sign_in(request: HttpRequest) -> JsonResponse:
    """Authenticate by email and establish a web session with a fixed expiry."""
    loginRequest = parse_json_request(request, LoginRequest)
    if isinstance(loginRequest, JsonResponse):
        return loginRequest

    try:
        strNormalizedEmail = UserManager.normalize_email(loginRequest.email)
        intRetryAfterSeconds = apply_login_rate_limit(
            request.META.get("REMOTE_ADDR", ""), normalizedEmail=strNormalizedEmail
        )
        if intRetryAfterSeconds:
            return build_rate_limited_response(intRetryAfterSeconds)

        # Django verifies passwords, rejects inactive users, and mitigates timing differences.
        user = cast(
            User | None,
            authenticate(
                request,
                email=strNormalizedEmail,
                password=loginRequest.password.get_secret_value(),
            ),
        )
        if user is None:
            return build_error_response(
                "invalid_credentials",
                "The email or password is incorrect.",
                statusCode=401,
            )

        with transaction.atomic():
            # Keep the same organization-before-account lock order as security writes.
            organization = _lock_session_audit_organization(user)
            login(request, user)
            sessionLifetime = (
                _REMEMBERED_SESSION_LIFETIME
                if loginRequest.remember_me
                else timedelta(seconds=settings.SESSION_COOKIE_AGE)
            )
            # Save the authorized session and audit together before reporting success.
            request.session.set_expiry(timezone.now() + sessionLifetime)
            request.session.save()
            record_audit(
                "account.login",
                actor=user,
                organization=organization,
                target=user,
            )
        # login() rotates the CSRF secret; return a token matching the new cookie.
        return _build_session_response(request, user)
    except (ImproperlyConfigured, DatabaseError):
        # Clean in-memory login whose transaction failed.
        request.session = type(request.session)()
        request.user = AnonymousUser()
        return build_service_unavailable_response()


@never_cache
@require_GET
def get_current_session(request: HttpRequest) -> JsonResponse:
    """Resolve the session and current account through Django's authentication middleware."""
    try:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        return _build_session_response(request, cast(User, request.user))
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()


@never_cache
@require_GET
def get_current_access(request: HttpRequest) -> JsonResponse:
    """Return organization and department display data for the authenticated session."""
    try:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        # The caller cannot select another account, organization, or credential channel.
        user = cast(User, request.user)
        accountAccessInfo = get_account_access_info(actorId=user.id)
        return JsonResponse(build_account_access_payload(accountAccessInfo))
    except PermissionDenied:
        return build_error_response(
            "organization_access_required",
            "Organization access is required.",
            statusCode=403,
        )
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()


@never_cache
@require_POST
def sign_out(request: HttpRequest) -> JsonResponse:
    """Revoke this browser session, including any tabs sharing its cookie."""
    try:
        with transaction.atomic():
            if request.user.is_authenticated:
                user = cast(User, request.user)
                organization = _lock_session_audit_organization(user)
                record_audit(
                    "account.logout",
                    actor=user,
                    organization=organization,
                    target=user,
                )
            logout(request)
    except (ImproperlyConfigured, DatabaseError):
        return build_service_unavailable_response()
    return JsonResponse(MessageResponse(message="Signed out.").model_dump(mode="python"))


@never_cache
@require_POST
@sensitive_post_parameters()
@sensitive_variables()
def sign_out_other_sessions(request: HttpRequest) -> JsonResponse:
    """Revoke other web sessions while keeping this session and its original expiry."""
    try:
        if not request.user.is_authenticated:
            return build_authentication_required_response()
        user = cast(User, request.user)
        revocationRequest = parse_json_request(request, SessionRevocationRequest)
        if isinstance(revocationRequest, JsonResponse):
            return revocationRequest

        intRetryAfterSeconds = apply_session_revocation_rate_limit(
            request.META.get("REMOTE_ADDR", ""), actorId=str(user.id)
        )
        if intRetryAfterSeconds:
            return build_rate_limited_response(intRetryAfterSeconds)

        strSessionAuthHash = cast(str, request.session.get(HASH_SESSION_KEY, ""))
        boolSessionWasModified = request.session.modified
        try:
            with transaction.atomic():
                user = revoke_other_sessions(
                    actorId=user.id,
                    channel=AccessChannel.SESSION,
                    currentPassword=revocationRequest.current_password.get_secret_value(),
                    sessionAuthHash=strSessionAuthHash,
                )
                if request.session.get_expiry_date() <= timezone.now():
                    raise SessionInvalidatedError("The current session has expired.")
                request.session[HASH_SESSION_KEY] = user.get_session_auth_hash()
                # Persist the kept session before committing the account's revocation version.
                request.session.save()
        except Exception:
            # Database rollback does not restore Django's in-memory session dictionary.
            request.session[HASH_SESSION_KEY] = strSessionAuthHash
            request.session.modified = boolSessionWasModified
            raise

        # Avoid a second write unless Django rotated the key while checking a fallback signing secret.
        request.session.modified = request.session.session_key != request.COOKIES.get(
            settings.SESSION_COOKIE_NAME
        )
        request.user = user
        return JsonResponse({"message": "Other sessions signed out."})
    except SessionInvalidatedError:
        return build_authentication_required_response(
            "The current session is no longer valid. Sign in again."
        )
    except ValidationError as e:
        return build_error_response(
            "invalid_session_revocation",
            "The current password is incorrect.",
            statusCode=400,
            fields=e.message_dict,
        )
    except PermissionDenied:
        return build_error_response(
            "session_revocation_unavailable",
            "This session operation is unavailable.",
            statusCode=403,
        )
    except (ImproperlyConfigured, DatabaseError, UpdateError):
        return build_service_unavailable_response()
