# FileName: http.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from collections.abc import Callable
from functools import wraps
from typing import Concatenate

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.http import HttpRequest, JsonResponse

from accounts.session_revocation import SessionInvalidatedError
from console_project.http import (
    build_error_response,
    build_authentication_required_response,
)


def handle_notification_errors[**P](
    view: Callable[Concatenate[HttpRequest, P], JsonResponse],
) -> Callable[Concatenate[HttpRequest, P], JsonResponse]:
    """Convert expected notification and recipient errors into HTTP responses."""

    @wraps(view)
    def wrapped(request: HttpRequest, *args: P.args, **kwargs: P.kwargs) -> JsonResponse:
        try:
            return view(request, *args, **kwargs)
        except SessionInvalidatedError:
            return build_authentication_required_response()
        except PermissionDenied:
            return build_error_response(
                "access_required", "Access is unavailable.", statusCode=403
            )
        except ObjectDoesNotExist:
            return build_error_response(
                "not_found", "This record is unavailable.", statusCode=404
            )
        except ValidationError as e:
            dictField = e.message_dict if hasattr(e, "error_dict") else None
            return build_error_response(
                "invalid_request",
                "One or more request fields are invalid."
                if dictField is not None
                else " ".join(e.messages),
                statusCode=400,
                fields=dictField,
            )

    return wrapped
