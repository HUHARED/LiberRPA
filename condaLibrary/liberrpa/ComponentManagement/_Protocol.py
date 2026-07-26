# FileName: _Protocol.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from liberrpa.ComponentManagement.Utils._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Utils._File import parse_json
from liberrpa.ComponentManagement.Utils._TypedValue import DictErrorResponse, DictProtocolResponse
from liberrpa.ComponentManagement._Publish import publish_component


_SET_REQUEST_KEYS = {"schemaVersion", "operation", "projectPath"}


def _parse_request(requestInfo: str) -> dict[str, object]:
    if requestInfo.strip() == "":
        raise ComponentManagementError(
            code="invalid_request",
            message="Component Management request cannot be empty.",
        )

    try:
        value = parse_json(requestInfo)
    except ValueError as e:
        raise ComponentManagementError(
            code="invalid_request",
            message="Component Management request must be valid JSON.",
            details={"reason": str(e)},
        ) from e

    if not isinstance(value, dict):
        raise ComponentManagementError(
            code="invalid_request",
            message="Component Management request root must be an object.",
        )

    if set(value) != _SET_REQUEST_KEYS:
        raise ComponentManagementError(
            code="invalid_request",
            message="Component Management request contains missing or unknown fields.",
            details={
                "missingFields": sorted(_SET_REQUEST_KEYS - set(value)),
                "unknownFields": sorted(set(value) - _SET_REQUEST_KEYS),
            },
        )

    if type(value.get("schemaVersion")) is not int or value.get("schemaVersion") != 1:
        raise ComponentManagementError(
            code="invalid_request",
            message="Only Component Management protocol schemaVersion 1 is supported.",
        )

    if value.get("operation") != "publishComponent":
        raise ComponentManagementError(
            code="invalid_request",
            message=f"Unsupported Component Management operation: {value.get('operation')!r}.",
        )

    if not isinstance(value.get("projectPath"), str) or str(value["projectPath"]).strip() == "":
        raise ComponentManagementError(
            code="invalid_request",
            message="projectPath must be a non-empty string.",
        )

    return value


def _build_error_response(errorObj: ComponentManagementError) -> DictErrorResponse:
    return {
        "schemaVersion": 1,
        "ok": False,
        "error": {
            "code": errorObj.code,
            "message": errorObj.message,
            "details": errorObj.details or {},
        },
    }


def handle_request(requestInfo: str) -> DictProtocolResponse:
    try:
        dictRequest = _parse_request(requestInfo)
        dictResult, listWarning = publish_component(str(dictRequest["projectPath"]))
        return {
            "schemaVersion": 1,
            "ok": True,
            "result": dictResult,
            "warnings": listWarning,
        }
    except ComponentManagementError as e:
        return _build_error_response(e)
