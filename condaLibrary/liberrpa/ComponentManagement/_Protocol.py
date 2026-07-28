# FileName: _Protocol.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from liberrpa.ComponentManagement.Utils._Exception import ComponentManagementError
from liberrpa.ComponentManagement.Utils._File import parse_json
from liberrpa.ComponentManagement.Utils._TypedValue import (
    DictComponentManagementRequest,
    DictErrorResponse,
    DictProtocolResponse,
    DictPublishComponentRequest,
    DictRepositoryIndexRebuiltResult,
    DictRebuildRepositoryIndexRequest,
    DictPublishComponentSuccessResponse,
    DictRepositoryIndexRebuiltSuccessResponse,
)
from liberrpa.ComponentManagement._Publish import publish_component
from liberrpa.ComponentManagement._Repository import rebuild_repository_index

from typing import cast


_SET_PUBLISH_REQUEST_KEYS = {"schemaVersion", "operation", "projectPath"}
_SET_REBUILD_REQUEST_KEYS = {"schemaVersion", "operation"}


def _parse_request(requestInfo: str) -> DictComponentManagementRequest:
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

    if type(value.get("schemaVersion")) is not int or value.get("schemaVersion") != 1:
        raise ComponentManagementError(
            code="invalid_request",
            message="Only Component Management protocol schemaVersion 1 is supported.",
        )

    operation = value.get("operation")
    if operation == "publishComponent":
        if set(value) != _SET_PUBLISH_REQUEST_KEYS:
            raise ComponentManagementError(
                code="invalid_request",
                message="Publish Component request contains missing or unknown fields.",
                details={
                    "missingFields": sorted(_SET_PUBLISH_REQUEST_KEYS - set(value)),
                    "unknownFields": sorted(set(value) - _SET_PUBLISH_REQUEST_KEYS),
                },
            )

        if not isinstance(value.get("projectPath"), str) or str(value["projectPath"]).strip() == "":
            raise ComponentManagementError(
                code="invalid_request",
                message="projectPath must be a non-empty string.",
            )

        return cast(DictPublishComponentRequest, value)

    if operation == "rebuildRepositoryIndex":
        if set(value) != _SET_REBUILD_REQUEST_KEYS:
            raise ComponentManagementError(
                code="invalid_request",
                message="Rebuild Repository Index request contains missing or unknown fields.",
                details={
                    "missingFields": sorted(_SET_REBUILD_REQUEST_KEYS - set(value)),
                    "unknownFields": sorted(set(value) - _SET_REBUILD_REQUEST_KEYS),
                },
            )

        return cast(DictRebuildRepositoryIndexRequest, value)

    raise ComponentManagementError(
        code="invalid_request",
        message=f"Unsupported Component Management operation: {operation!r}.",
    )


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

        if dictRequest["operation"] == "publishComponent":
            publishResult, listWarning = publish_component(dictRequest["projectPath"])

            responsePublish: DictPublishComponentSuccessResponse = {
                "schemaVersion": 1,
                "ok": True,
                "result": publishResult,
                "warnings": listWarning,
            }
            return responsePublish

        # dictRequest["operation"] == "rebuildRepositoryIndex"
        rebuildResult = rebuild_repository_index()

        dictRebuildResult: DictRepositoryIndexRebuiltResult = {
            "status": "repositoryIndexRebuilt",
            "componentCount": rebuildResult.componentCount,
            "versionCount": rebuildResult.versionCount,
        }

        responseRebuilt: DictRepositoryIndexRebuiltSuccessResponse = {
            "schemaVersion": 1,
            "ok": True,
            "result": dictRebuildResult,
            "warnings": rebuildResult.warnings,
        }
        return responseRebuilt

    except ComponentManagementError as e:
        return _build_error_response(e)
