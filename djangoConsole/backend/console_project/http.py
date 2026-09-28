# FileName: http.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import json
import logging

from django.http import HttpRequest, JsonResponse, QueryDict
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_variables
from pydantic import BaseModel

_LOGGER = logging.getLogger("console.http")
_DEFAULT_MAX_JSON_BODY_BYTES = 4096


def build_error_response(
    errorCode: str,
    errorMessage: str,
    *,
    statusCode: int,
    fields: dict[str, list[str]] | None = None,
) -> JsonResponse:
    dictErrorDetail: dict[str, object] = {"code": errorCode, "message": errorMessage}
    if fields is not None:
        dictErrorDetail["fields"] = fields
    return JsonResponse({"error": dictErrorDetail}, status=statusCode)


def build_service_unavailable_response() -> JsonResponse:
    _LOGGER.exception("Service temporarily unavailable.")
    return build_error_response(
        "service_unavailable", "The service is temporarily unavailable.", statusCode=503
    )


def build_rate_limited_response(retryAfterSeconds: int) -> JsonResponse:
    response = build_error_response(
        "rate_limited", "Too many requests. Try again later.", statusCode=429
    )
    response["Retry-After"] = str(retryAfterSeconds)
    return response


@sensitive_variables()
def parse_json_request[Payload: BaseModel](
    request: HttpRequest,
    requestSchema: type[Payload],
    *,
    maxBodyBytes: int = _DEFAULT_MAX_JSON_BODY_BYTES,
) -> Payload | JsonResponse:
    """Parse and validate an untrusted HTTP body into the requested schema."""

    def parse_json_object(fieldPairs: list[tuple[str, object]]) -> dict[str, object]:
        dictJsonField: dict[str, object] = {}
        for strFieldName, fieldValue in fieldPairs:
            if strFieldName in dictJsonField:
                raise ValueError("Duplicate JSON fields are not allowed.")
            # Reject escaped lone surrogates before strings reach hashing or the database.
            strFieldName.encode("utf-8")
            if isinstance(fieldValue, str):
                fieldValue.encode("utf-8")
            dictJsonField[strFieldName] = fieldValue
        return dictJsonField

    if request.content_type != "application/json":
        return build_error_response(
            "unsupported_media_type", "Send application/json.", statusCode=415
        )

    requestBody = request.read(maxBodyBytes + 1)
    if len(requestBody) > maxBodyBytes:
        return build_error_response(
            "request_too_large", "The request body is too large.", statusCode=413
        )
    try:
        return requestSchema.model_validate(
            json.loads(requestBody.decode("utf-8"), object_pairs_hook=parse_json_object)
        )
    except (ValueError, RecursionError):
        return build_error_response(
            "invalid_request",
            "Send a JSON object with the required fields, correct types, and no unknown fields.",
            statusCode=400,
        )


def parse_page_number(query: QueryDict) -> int:
    """Parse a single positive page number; the view keeps its own error code and message."""
    listPageValue = query.getlist("page")
    if not listPageValue:
        return 1
    strPageValue = listPageValue[0]
    if (
        len(listPageValue) != 1
        or not strPageValue.isascii()
        or not strPageValue.isdecimal()
        or len(strPageValue) > 9
        or int(strPageValue) < 1
    ):
        raise ValueError("Send one positive integer page number.")
    return int(strPageValue)


@never_cache
def csrf_failure(request: HttpRequest, reason: str = "") -> JsonResponse:  # noqa: ARG001
    """Give browser clients a stable error without exposing internal rejection details."""
    # Django requires this signature; neither request data nor its reason is disclosed.
    return build_error_response(
        "csrf_failed",
        "Your request could not be verified. Please submit the form again.",
        statusCode=403,
    )
