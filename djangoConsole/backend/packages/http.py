# FileName: http.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from functools import wraps
from collections.abc import Callable
from typing import cast, Concatenate

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.core.paginator import InvalidPage
from django.db import DatabaseError
from django.db.models.deletion import ProtectedError
from django.http import HttpRequest, JsonResponse, HttpResponseBase
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt

from accounts.models import User
from accounts.resource_authentication import (
    authenticate_resource_request,
    InvalidResourceCredentialError,
)
from accounts.session_revocation import SessionInvalidatedError
from console_project.http import (
    build_error_response,
    build_authentication_required_response,
    build_service_unavailable_response,
)
from file_storage.services import FileOperationError
from organizations.permissions import AccessChannel, get_current_membership
from shared_files.http import FileRequestError, FileAuthentication


def build_package_error(e: Exception) -> JsonResponse:
    if isinstance(e, (SessionInvalidatedError, InvalidResourceCredentialError)):
        return build_authentication_required_response()
    if isinstance(e, PermissionDenied):
        return build_error_response(
            "package_access_required", "Package access is unavailable.", statusCode=403
        )
    if isinstance(e, ObjectDoesNotExist):
        return build_error_response(
            "package_not_found",
            "The Package, department, or transfer is unavailable.",
            statusCode=404,
        )
    if isinstance(e, FileOperationError):
        return build_error_response(e.code, str(e), statusCode=e.status)
    if isinstance(e, ProtectedError):
        return build_error_response(
            "package_in_use", "This Package still has active references.", statusCode=409
        )
    if isinstance(e, (ValueError, FileRequestError, ValidationError, InvalidPage)):
        return build_error_response(
            "invalid_package_request",
            " ".join(e.messages) if isinstance(e, ValidationError) else str(e),
            statusCode=400,
        )
    return build_service_unavailable_response()


def package_view[**P](
    view: Callable[Concatenate[HttpRequest, FileAuthentication, P], HttpResponseBase],
    *,
    channel: AccessChannel = AccessChannel.SESSION,
) -> Callable[Concatenate[HttpRequest, P], HttpResponseBase]:
    @never_cache
    @wraps(view)
    def wrapped(
        request: HttpRequest, *args: P.args, **kwargs: P.kwargs
    ) -> HttpResponseBase:
        try:
            if channel == AccessChannel.SESSION:
                if not request.user.is_authenticated:
                    return build_authentication_required_response()
                authentication = get_current_membership(
                    actorId=cast(User, request.user).pk
                )
            else:
                authentication = authenticate_resource_request(request)
                if isinstance(authentication, JsonResponse):
                    return authentication
                if authentication.access.channel != channel:
                    raise PermissionDenied("Use the requested native client session.")
            return view(request, authentication, *args, **kwargs)
        except (
            ObjectDoesNotExist,
            PermissionDenied,
            ValidationError,
            InvalidPage,
            FileOperationError,
            FileRequestError,
            ValueError,
            SessionInvalidatedError,
            InvalidResourceCredentialError,
            DatabaseError,
            OSError,
        ) as e:
            return build_package_error(e)

    return csrf_exempt(wrapped) if channel != AccessChannel.SESSION else wrapped
