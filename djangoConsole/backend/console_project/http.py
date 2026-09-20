# FileName: http.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import json

from django.http import HttpRequest, JsonResponse
from django.views.decorators.debug import sensitive_variables
from pydantic import BaseModel, ConfigDict

_INT_MAX_JSON_BODY_BYTES = 4096


class JsonRequest(BaseModel):
    """Validate HTTP envelopes; application services own business validation."""

    model_config = ConfigDict(
        strict=True, extra="forbid", frozen=True, hide_input_in_errors=True
    )


def _parse_json_object(fieldPairs: list[tuple[str, object]]) -> dict[str, object]:
    dictJsonField: dict[str, object] = {}
    for fieldName, fieldValue in fieldPairs:
        if fieldName in dictJsonField:
            raise ValueError("Duplicate JSON fields are not allowed.")
        # Reject escaped lone surrogates before strings reach hashing or the database.
        fieldName.encode("utf-8")
        if isinstance(fieldValue, str):
            fieldValue.encode("utf-8")
        dictJsonField[fieldName] = fieldValue
    return dictJsonField


def build_error_response(
    errorCode: str, errorMessage: str, *, statusCode: int
) -> JsonResponse:
    return JsonResponse(
        {"error": {"code": errorCode, "message": errorMessage}}, status=statusCode
    )


@sensitive_variables()
def parse_json_request[Payload: BaseModel](
    request: HttpRequest,
    requestSchema: type[Payload],
    *,
    maxBodyBytes: int = _INT_MAX_JSON_BODY_BYTES,
) -> Payload | JsonResponse:
    """Parse and validate an untrusted HTTP body into the requested schema."""
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
            json.loads(requestBody.decode("utf-8"), object_pairs_hook=_parse_json_object)
        )
    except (ValueError, RecursionError):
        return build_error_response(
            "invalid_request",
            "Send a JSON object with the required fields, correct types, and no unknown fields.",
            statusCode=400,
        )


def build_rate_limited_response(retryAfterSeconds: int) -> JsonResponse:
    response = build_error_response(
        "rate_limited", "Too many requests. Try again later.", statusCode=429
    )
    response["Retry-After"] = str(retryAfterSeconds)
    return response
