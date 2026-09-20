# FileName: session_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import timedelta
from typing import cast

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.db import DatabaseError
from django.http import HttpRequest, JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_variables
from django.views.decorators.http import require_GET, require_POST
from pydantic import SecretStr

from organizations.access import get_account_access_info
from organizations.http import build_account_access_payload

from .http import (
    AccountRequest,
    build_error_response,
    build_rate_limited_response,
    parse_json_request,
)
from .models import User, UserManager
from .rate_limits import reserve_login_request

_REMEMBERED_SESSION_LIFETIME = timedelta(days=14)


class LoginRequest(AccountRequest):
    email: str
    password: SecretStr
    remember_me: bool = False


def _build_session_response(request: HttpRequest, user: User) -> JsonResponse:
    # Return current identity only; business operations resolve their own current permissions.
    return JsonResponse({
        "user": {"id": user.id, "email": user.email, "username": user.username},
        "expires_at": request.session.get_expiry_date(),
        "csrf_token": get_token(request),
    })


def _build_service_unavailable_response() -> JsonResponse:
    return build_error_response(
        "service_unavailable", "The service is temporarily unavailable.", statusCode=503
    )


@never_cache
@require_POST
@sensitive_variables()
def sign_in(request: HttpRequest) -> JsonResponse:
    """Authenticate by email and establish a web session with a fixed expiry."""
    loginRequest = parse_json_request(request, LoginRequest)
    if isinstance(loginRequest, JsonResponse):
        return loginRequest
    try:
        normalizedEmail = UserManager.normalize_email(loginRequest.email)
        retryAfterSeconds = reserve_login_request(
            request.META.get("REMOTE_ADDR", ""), normalizedEmail=normalizedEmail
        )
        if retryAfterSeconds:
            return build_rate_limited_response(retryAfterSeconds)

        # Django verifies passwords, rejects inactive users, and mitigates timing differences.
        user = cast(
            User | None,
            authenticate(
                request,
                email=normalizedEmail,
                password=loginRequest.password.get_secret_value(),
            ),
        )
        if user is None:
            return build_error_response(
                "invalid_credentials",
                "The email or password is incorrect.",
                statusCode=401,
            )

        login(request, user)
        sessionLifetime = (
            _REMEMBERED_SESSION_LIFETIME
            if loginRequest.remember_me
            else timedelta(seconds=settings.SESSION_COOKIE_AGE)
        )
        # An absolute datetime prevents later session writes from extending this login.
        request.session.set_expiry(timezone.now() + sessionLifetime)
        # login() rotates the CSRF secret; return a token matching the new cookie.
        return _build_session_response(request, user)
    except (ImproperlyConfigured, DatabaseError):
        return _build_service_unavailable_response()


@never_cache
@require_GET
def get_current_session(request: HttpRequest) -> JsonResponse:
    """Resolve the session and current account through Django's authentication middleware."""
    try:
        if not request.user.is_authenticated:
            return build_error_response(
                "authentication_required", "Sign in to continue.", statusCode=401
            )
        return _build_session_response(request, cast(User, request.user))
    except (ImproperlyConfigured, DatabaseError):
        return _build_service_unavailable_response()


@never_cache
@require_GET
def get_current_access(request: HttpRequest) -> JsonResponse:
    """Return organization and department display data for the authenticated session."""
    try:
        if not request.user.is_authenticated:
            return build_error_response(
                "authentication_required", "Sign in to continue.", statusCode=401
            )
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
        return _build_service_unavailable_response()


@never_cache
@require_POST
def sign_out(request: HttpRequest) -> JsonResponse:
    """Revoke this browser session, including any tabs sharing its cookie."""
    try:
        logout(request)
    except (ImproperlyConfigured, DatabaseError):
        return _build_service_unavailable_response()
    return JsonResponse({"message": "Signed out."})
