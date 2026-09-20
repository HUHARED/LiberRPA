# FileName: http.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import json

from django.http import HttpRequest, JsonResponse
from django.views.decorators.debug import sensitive_variables
from pydantic import BaseModel, ConfigDict

_MAX_ACCOUNT_BODY_BYTES = 4096


class AccountRequest(BaseModel):
    """Validate account HTTP envelopes; application services own business validation."""

    model_config = ConfigDict(
        strict=True, extra="forbid", frozen=True, hide_input_in_errors=True
    )


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("Duplicate JSON fields are not allowed.")
        # Reject escaped lone surrogates before strings reach hashing or the database.
        name.encode("utf-8")
        if isinstance(value, str):
            value.encode("utf-8")
        result[name] = value
    return result


def error_response(code: str, message: str, *, statusCode: int) -> JsonResponse:
    return JsonResponse({"error": {"code": code, "message": message}}, status=statusCode)


@sensitive_variables()
def read_json_request[Payload: BaseModel](
    request: HttpRequest, schema: type[Payload]
) -> Payload | JsonResponse:
    if request.content_type != "application/json":
        return error_response(
            "unsupported_media_type", "Send application/json.", statusCode=415
        )

    body = request.read(_MAX_ACCOUNT_BODY_BYTES + 1)
    if len(body) > _MAX_ACCOUNT_BODY_BYTES:
        return error_response(
            "request_too_large", "The request body is too large.", statusCode=413
        )
    try:
        return schema.model_validate(
            json.loads(body.decode("utf-8"), object_pairs_hook=_unique_json_object)
        )
    except (ValueError, RecursionError):
        return error_response(
            "invalid_request",
            "Send a JSON object with the required fields, correct types, and no unknown fields.",
            statusCode=400,
        )


def rate_limited_response(retryAfter: int) -> JsonResponse:
    response = error_response(
        "rate_limited", "Too many requests. Try again later.", statusCode=429
    )
    response["Retry-After"] = str(retryAfter)
    return response
