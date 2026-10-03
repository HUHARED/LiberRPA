# FileName: _ConsoleHttp.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import json
import math
import time
from contextlib import contextmanager
from collections.abc import Callable, Generator
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, TypeVar

import requests

from liberrpa.Common._ConsoleContext import get_console_context

INT_MAX_JSON_BYTES = 2 * 1024 * 1024
_SET_RETRY_STATUS_CODE = frozenset({408, 429, 500, 502, 503, 504})
_TUPLE_RETRY_DELAY_SECONDS = (1.0, 3.0)
_FLOAT_MAX_RETRY_WAIT_SECONDS = 30.0
_OperationResult = TypeVar("_OperationResult")


class ConsoleError(RuntimeError):
    """A Console request failed; requestId identifies the operation for diagnostics."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        statusCode: int | None = None,
        requestId: str | None = None,
        retryAfter: float | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.statusCode = statusCode
        self.requestId = requestId
        self.retryAfter = retryAfter


class RetryBudget:
    """Share at most two additional attempts and 30 seconds of waiting per operation."""

    def __init__(self) -> None:
        self.retryCount = 0
        self.waitSeconds = 0.0

    def run(self, operation: Callable[[], _OperationResult]) -> _OperationResult:
        while True:
            try:
                return operation()
            except ConsoleError as e:
                if (
                    e.code != "connection_error"
                    and e.statusCode not in _SET_RETRY_STATUS_CODE
                ) or self.retryCount >= len(_TUPLE_RETRY_DELAY_SECONDS):
                    raise

                floatDelaySeconds = max(
                    _TUPLE_RETRY_DELAY_SECONDS[self.retryCount], e.retryAfter or 0.0
                )
                if self.waitSeconds + floatDelaySeconds > _FLOAT_MAX_RETRY_WAIT_SECONDS:
                    raise

                self.retryCount += 1
                self.waitSeconds += floatDelaySeconds
                time.sleep(floatDelaySeconds)


def encode_json(value: object) -> bytes:
    """Encode one JSON boundary; reject non-JSON values instead of stringifying them."""
    try:
        requestBodyBytes = json.dumps(
            value, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise ValueError("Console values must be valid JSON values.") from None

    if len(requestBodyBytes) > INT_MAX_JSON_BYTES:
        raise ValueError(
            "The complete Console JSON request cannot exceed 2 MiB; split the batch explicitly."
        )

    return requestBodyBytes


def _parse_retry_after(retryAfterValue: str | None) -> float | None:
    if retryAfterValue is None:
        return None

    try:
        floatRetryAfterSeconds = float(retryAfterValue)
        return (
            max(0.0, floatRetryAfterSeconds)
            if math.isfinite(floatRetryAfterSeconds)
            else None
        )

    except ValueError:
        try:
            datetimeRetryAfter = parsedate_to_datetime(retryAfterValue)
            return max(0.0, (datetimeRetryAfter - datetime.now(UTC)).total_seconds())

        except (ValueError, TypeError, OverflowError):
            return None


def read_json_response(
    response: requests.Response, requestId: str | None = None
) -> dict[str, Any]:
    listResponseChunk: list[bytes] = []
    intResponseSizeBytes = 0
    for responseChunkBytes in response.iter_content(chunk_size=65536):
        intResponseSizeBytes += len(responseChunkBytes)
        if intResponseSizeBytes > INT_MAX_JSON_BYTES:
            raise ConsoleError(
                "response_too_large",
                "The Console JSON response exceeds 2 MiB.",
                requestId=requestId,
            )

        listResponseChunk.append(responseChunkBytes)

    try:
        responseValue = json.loads(b"".join(listResponseChunk))

    except (ValueError, UnicodeError):
        responseValue = None

    if not 200 <= response.status_code < 300:
        errorValue = (
            responseValue.get("error") if isinstance(responseValue, dict) else None
        )
        if isinstance(errorValue, dict) and isinstance(errorValue.get("message"), str):
            strErrorMessage = errorValue["message"]
            strErrorCode = errorValue.get("code", "http_error")
            if not isinstance(strErrorCode, str):
                strErrorCode = "http_error"

        else:
            strErrorMessage = f"The Console request failed (HTTP {response.status_code})."
            strErrorCode = "http_error"

        raise ConsoleError(
            strErrorCode,
            strErrorMessage,
            statusCode=response.status_code,
            requestId=requestId,
            retryAfter=_parse_retry_after(response.headers.get("Retry-After")),
        )

    if not isinstance(responseValue, dict):
        raise ConsoleError(
            "invalid_response",
            "Console returned an invalid JSON object.",
            requestId=requestId,
        )

    return responseValue


@contextmanager
def open_response(
    method: str,
    path: str,
    *,
    body: bytes | None = None,
    contentType: str = "application/json",
    headers: dict[str, str] | None = None,
) -> Generator[requests.Response]:
    consoleContext = get_console_context()
    dictHeaders = {
        "Authorization": f"Bearer {consoleContext.token}",
        "Accept": "application/json",
        "Accept-Encoding": "identity",
        "Content-Type": contentType,
        **(headers or {}),
    }
    with requests.Session() as httpSession:
        # Console uses the original native credential; .netrc must not replace it.
        httpSession.trust_env = False
        with httpSession.request(
            method,
            f"{consoleContext.consoleUrl.rstrip('/')}/api/v1/{path}",
            data=body,
            headers=dictHeaders,
            timeout=(10, 60),
            allow_redirects=False,
            stream=True,
        ) as response:
            yield response


def request_json(
    path: str,
    payload: dict[str, object] | None = None,
    *,
    method: str = "POST",
    body: bytes | None = None,
    contentType: str = "application/json",
    headers: dict[str, str] | None = None,
    retryBudget: RetryBudget | None = None,
    requestId: str | None = None,
) -> dict[str, Any]:
    if body is None and payload is not None:
        body = encode_json(payload)

    def _perform_request() -> dict[str, Any]:
        try:
            with open_response(
                method, path, body=body, contentType=contentType, headers=headers
            ) as response:
                return read_json_response(response, requestId)
        except requests.RequestException:
            raise ConsoleError(
                "connection_error",
                "Could not complete the Console request.",
                requestId=requestId,
            ) from None

    try:
        return (
            retryBudget.run(_perform_request)
            if retryBudget is not None
            else _perform_request()
        )
    except ConsoleError as e:
        if requestId is not None and (
            e.code in {"connection_error", "invalid_response", "response_too_large"}
            or e.statusCode in _SET_RETRY_STATUS_CODE
            or (retryBudget is not None and retryBudget.retryCount > 0)
        ):
            raise ConsoleError(
                e.code,
                f"{e} The operation may already have completed; check Console before starting it again.",
                statusCode=e.statusCode,
                requestId=requestId,
                retryAfter=e.retryAfter,
            ) from None
        raise
