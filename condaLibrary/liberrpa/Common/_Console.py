# FileName: _Console.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import hashlib
import os
import tempfile
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, cast, get_args
from uuid import UUID, uuid4

from liberrpa.Common._TypedValue import JsonValue, StrPath
from liberrpa.Common._ConsoleHttp import (
    INT_MAX_JSON_BYTES,
    ConsoleError,
    RetryBudget,
    encode_json,
    read_json_response,
    open_response,
    request_json,
)
from liberrpa.Data import sanitize_filename


_INT_MAX_BATCH_ITEMS = 100
_INT_MAX_QUEUE_ITEM_BYTES = 1024 * 1024
_INT_MAX_SHARED_FILE_BYTES = 20 * 1024 * 1024
_INT_FILE_CHUNK_BYTES = 4 * 1024 * 1024


type DataQueueItemStatus = Literal["unclaimed", "claimed"]
type DataQueueItemFilterStatus = Literal["all", "unclaimed", "claimed"]
type DataQueueItemOrder = Literal["oldest_first", "newest_first"]
type SharedFileSort = Literal["name", "size", "uploaded_at"]
type SortOrder = Literal["asc", "desc"]


class _DataQueueMutationOperation(StrEnum):
    CLAIM = "claim"
    RESET = "reset"
    DELETE_ITEMS = "delete_items"


class _SharedFileUploadState(StrEnum):
    RECEIVING = "receiving"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELED = "canceled"


@dataclass(frozen=True)
class Credential:
    """Secret fields are deliberately excluded from the object representation."""

    username: str = field(repr=False)
    password: str = field(repr=False)


@dataclass(frozen=True)
class DataQueueItem:
    id: str
    data: JsonValue = field(repr=False)


@dataclass(frozen=True)
class DataQueueItemDetails(DataQueueItem):
    sequence: int
    status: DataQueueItemStatus
    dataSummary: str = field(repr=False)
    uploadedById: str
    uploadedByName: str
    uploadedAt: datetime
    lastClaimedById: str | None
    lastClaimedByName: str
    lastClaimedAt: datetime | None


@dataclass(frozen=True)
class DataQueuePage:
    items: list[DataQueueItemDetails]
    nextAfterSequence: int | None


@dataclass(frozen=True)
class DataQueueMutationResult:
    requestId: str
    acceptedAt: datetime
    itemIds: list[str]
    missingIds: list[str]
    skippedIds: list[str]
    items: list[DataQueueItem]
    deduplicated: bool


class DataQueueClaimReplayError(ConsoleError):
    """The original claim is known, but some claimed data has since been deleted."""

    def __init__(self, result: DataQueueMutationResult) -> None:
        super().__init__(
            "claim_items_missing",
            "Some items from the original claim no longer exist. Inspect result; no replacement items were claimed.",
            requestId=result.requestId,
        )
        self.result = result


@dataclass(frozen=True)
class SharedFileInfo:
    path: str
    name: str
    departmentPath: str
    sizeBytes: int
    sha256: str
    uploadedByName: str
    uploadedAt: datetime


@dataclass(frozen=True)
class SharedFileUsage:
    usedBytes: int
    reservedBytes: int
    pendingCleanupBytes: int
    limitBytes: int
    maxFileBytes: int


@dataclass(frozen=True)
class SharedFilePage:
    files: list[SharedFileInfo]
    departmentPath: str | None
    usage: SharedFileUsage
    page: int
    pageSize: int
    totalCount: int
    totalPages: int


@dataclass(frozen=True)
class SharedFileDeleteResult:
    requestId: str
    deletedPaths: list[str]
    missingPaths: list[str]
    deletedCount: int


def _validate_choice(value: str, choices: tuple[str, ...], parameterName: str) -> None:
    if value not in choices:
        raise ValueError(f"{parameterName} must be one of {choices}.")


def _validate_batch_items(items: list[Any]) -> None:
    if not isinstance(items, list) or not 1 <= len(items) <= _INT_MAX_BATCH_ITEMS:
        raise ValueError(
            "Supply a list containing between 1 and 100 items; split larger batches explicitly."
        )


def _parse_data_queue_selection(
    status: DataQueueItemFilterStatus,
    order: DataQueueItemOrder,
    count: int,
) -> dict[str, object]:
    if type(count) is not int or not 1 <= count <= _INT_MAX_BATCH_ITEMS:
        raise ValueError("count must be an integer between 1 and 100.")
    _validate_choice(status, get_args(DataQueueItemFilterStatus.__value__), "status")
    _validate_choice(order, get_args(DataQueueItemOrder.__value__), "order")
    return {
        "status": status,
        "order": order,
        "count": count,
    }


def _normalize_queue_item_ids(itemIds: str | list[str]) -> list[str]:
    listItemId = [itemIds] if isinstance(itemIds, str) else itemIds
    _validate_batch_items(listItemId)
    return [str(UUID(strItemId)) for strItemId in listItemId]


def _parse_data_queue_item_details(responseBody: dict[str, Any]) -> DataQueueItemDetails:
    _validate_choice(
        responseBody["status"], get_args(DataQueueItemStatus.__value__), "status"
    )
    return DataQueueItemDetails(
        id=responseBody["id"],
        data=responseBody["data"],
        sequence=responseBody["sequence"],
        status=cast(DataQueueItemStatus, responseBody["status"]),
        dataSummary=responseBody["data_summary"],
        uploadedById=responseBody["uploaded_by_id"],
        uploadedByName=responseBody["uploaded_by_name"],
        uploadedAt=datetime.fromisoformat(responseBody["uploaded_at"]),
        lastClaimedById=responseBody["last_claimed_by_id"],
        lastClaimedByName=responseBody["last_claimed_by_name"],
        lastClaimedAt=(
            datetime.fromisoformat(responseBody["last_claimed_at"])
            if responseBody["last_claimed_at"] is not None
            else None
        ),
    )


def _parse_data_queue_mutation_result(
    responseBody: dict[str, Any],
) -> DataQueueMutationResult:
    return DataQueueMutationResult(
        requestId=responseBody["request_id"],
        acceptedAt=datetime.fromisoformat(responseBody["accepted_at"]),
        itemIds=responseBody["item_ids"],
        missingIds=responseBody["missing_ids"],
        skippedIds=responseBody["skipped_ids"],
        items=[
            DataQueueItem(id=dictItem["id"], data=dictItem["data"])
            for dictItem in responseBody["items"]
        ],
        deduplicated=responseBody["deduplicated"],
    )


def _mutate_data_queue_items(
    operation: _DataQueueMutationOperation,
    queuePath: str,
    requestBody: dict[str, object],
) -> DataQueueMutationResult:
    strRequestId = str(uuid4())
    return _parse_data_queue_mutation_result(
        request_json(
            f"data-queues/{operation}/",
            {"queue_path": queuePath, "request_id": strRequestId, **requestBody},
            retryBudget=RetryBudget(),
            requestId=strRequestId,
        )
    )


def _upload_data_queue_items(
    queuePath: str,
    items: list[JsonValue],
) -> DataQueueMutationResult:
    _validate_batch_items(items)
    strRequestId = str(uuid4())
    requestHeaderBytes = encode_json({
        "queue_path": queuePath,
        "request_id": strRequestId,
    })
    listItemJsonBytes: list[bytes] = []
    intRequestSizeBytes = len(requestHeaderBytes) + len(b',"items":[]')
    for itemValue in items:
        itemJsonBytes = encode_json(itemValue)
        if len(itemJsonBytes) > _INT_MAX_QUEUE_ITEM_BYTES:
            raise ValueError("A queue item cannot exceed 1 MiB of UTF-8 JSON.")
        intRequestSizeBytes += len(itemJsonBytes) + bool(listItemJsonBytes)
        if intRequestSizeBytes > INT_MAX_JSON_BYTES:
            raise ValueError(
                "The complete Console JSON request cannot exceed 2 MiB; split the batch explicitly."
            )
        listItemJsonBytes.append(itemJsonBytes)
    requestBodyBytes = (
        requestHeaderBytes[:-1] + b',"items":[' + b",".join(listItemJsonBytes) + b"]}"
    )
    return _parse_data_queue_mutation_result(
        request_json(
            "data-queues/upload/",
            body=requestBodyBytes,
            retryBudget=RetryBudget(),
            requestId=strRequestId,
        )
    )


def _parse_shared_file_info(responseBody: dict[str, Any]) -> SharedFileInfo:
    fileInfo = SharedFileInfo(
        path=responseBody["path"],
        name=responseBody["name"],
        departmentPath=responseBody["department_path"],
        sizeBytes=responseBody["size_bytes"],
        sha256=responseBody["sha256"],
        uploadedByName=responseBody["uploaded_by_name"],
        uploadedAt=datetime.fromisoformat(responseBody["uploaded_at"]),
    )
    if (
        type(fileInfo.sizeBytes) is not int
        or not 0 <= fileInfo.sizeBytes <= _INT_MAX_SHARED_FILE_BYTES
        or len(fileInfo.sha256) != 64
        or any(strCharacter not in "0123456789abcdef" for strCharacter in fileInfo.sha256)
    ):
        raise ConsoleError(
            "invalid_response", "Console returned invalid file size or checksum metadata."
        )
    return fileInfo


def _upload_shared_file(
    localPath: StrPath,
    path: str,
    *,
    overwrite: bool = False,
) -> SharedFileInfo:
    if type(overwrite) is not bool:
        raise ValueError("overwrite must be a bool.")
    strRequestId = str(uuid4())
    retryBudget = RetryBudget()
    with open(localPath, "rb") as sourceFile:
        intFileSizeBytes = os.fstat(sourceFile.fileno()).st_size
        if intFileSizeBytes > _INT_MAX_SHARED_FILE_BYTES:
            raise ValueError("A Shared File cannot exceed 20 MiB.")
        strChecksum = hashlib.file_digest(sourceFile, "sha256").hexdigest()
        dictUpload = request_json(
            "shared-files/uploads/",
            {
                "path": path,
                "request_id": strRequestId,
                "size_bytes": intFileSizeBytes,
                "sha256": strChecksum,
                "overwrite": overwrite,
            },
            retryBudget=retryBudget,
            requestId=strRequestId,
        )
        strUploadId = str(UUID(dictUpload["upload_id"]))
        uploadState = _SharedFileUploadState(dictUpload["state"])
        if uploadState == _SharedFileUploadState.COMPLETED:
            return _parse_shared_file_info(dictUpload["file"])
        if uploadState != _SharedFileUploadState.RECEIVING:
            raise ConsoleError(
                "upload_unavailable",
                "The original upload is no longer available.",
                requestId=strRequestId,
            )
        try:
            intOffset = dictUpload["offset"]
            intChunkBytes = dictUpload["chunk_bytes"]
            if (
                type(intOffset) is not int
                or not 0 <= intOffset <= intFileSizeBytes
                or intChunkBytes != _INT_FILE_CHUNK_BYTES
            ):
                raise ConsoleError(
                    "invalid_response",
                    "Console returned invalid upload progress.",
                    requestId=strRequestId,
                )
            sourceFile.seek(intOffset)
            while intOffset < intFileSizeBytes:
                fileChunkBytes = sourceFile.read(
                    min(intChunkBytes, intFileSizeBytes - intOffset)
                )
                if not fileChunkBytes:
                    raise ConsoleError(
                        "local_file_changed",
                        "The local file changed during upload.",
                        requestId=strRequestId,
                    )
                dictUpload = request_json(
                    f"shared-files/uploads/{strUploadId}/chunks/{intOffset}/",
                    method="PUT",
                    body=fileChunkBytes,
                    contentType="application/octet-stream",
                    headers={
                        "X-Chunk-SHA256": hashlib.sha256(fileChunkBytes).hexdigest()
                    },
                    retryBudget=retryBudget,
                    requestId=strRequestId,
                )
                intOffset += len(fileChunkBytes)
                if dictUpload["offset"] != intOffset:
                    raise ConsoleError(
                        "invalid_response",
                        "Console returned unexpected upload progress.",
                        requestId=strRequestId,
                    )
            dictUpload = request_json(
                f"shared-files/uploads/{strUploadId}/complete/",
                {},
                retryBudget=retryBudget,
                requestId=strRequestId,
            )
            return _parse_shared_file_info(dictUpload["file"])
        except BaseException:
            # Failed uploads no longer need their server-side transfer slot or reserved storage.
            try:
                request_json(f"shared-files/uploads/{strUploadId}/cancel/", {})
            except Exception:
                # Preserve the original failure; Console expires unreachable uploads.
                pass
            raise


def _download_shared_file(
    path: str,
    folderPath: StrPath,
    *,
    filename: str | None = None,
    overwrite: bool = False,
) -> str:
    if type(overwrite) is not bool:
        raise ValueError("overwrite must be a bool.")
    if filename is not None and not isinstance(filename, str):
        raise ValueError("filename must be a string or None.")

    strFilename = sanitize_filename(filename) if filename is not None else None
    pathFolder = Path(folderPath).absolute()
    pathFolder.mkdir(parents=True, exist_ok=True)

    # Retries keep the first response's filename and content identity.
    expectedFileInfo: SharedFileInfo | None = None

    def _download_file() -> str:
        nonlocal expectedFileInfo

        dictTransfer = request_json("shared-files/downloads/", {"path": path})
        strTransferId = str(UUID(dictTransfer["transfer_id"]))
        try:
            fileInfo = _parse_shared_file_info(dictTransfer["file"])
            if expectedFileInfo is None:
                expectedFileInfo = fileInfo
            elif (
                fileInfo.sha256 != expectedFileInfo.sha256
                or fileInfo.sizeBytes != expectedFileInfo.sizeBytes
            ):
                raise ConsoleError(
                    "file_changed",
                    "The Shared File changed while retrying; the destination was preserved.",
                )

            pathDestination = pathFolder / (
                strFilename
                if strFilename is not None
                else sanitize_filename(expectedFileInfo.name)
            )
            if not overwrite and pathDestination.exists():
                raise FileExistsError(
                    f"The destination already exists: {pathDestination}"
                )

            intTemporaryFileDescriptor, strTemporaryPath = tempfile.mkstemp(
                prefix=f".{pathDestination.name}.",
                suffix=".download",
                dir=pathDestination.parent,
            )
            os.close(intTemporaryFileDescriptor)
            pathTemporary = Path(strTemporaryPath)
            try:
                with open_response(
                    "GET",
                    f"shared-files/downloads/{strTransferId}/",
                    headers={"Accept": "application/octet-stream"},
                ) as response:
                    if not 200 <= response.status_code < 300:
                        read_json_response(response)

                    checksumHasher = hashlib.sha256()
                    intDownloadedBytes = 0

                    with pathTemporary.open("wb") as temporaryFile:
                        for fileChunkBytes in response.iter_content(chunk_size=65536):
                            intDownloadedBytes += len(fileChunkBytes)
                            if intDownloadedBytes > expectedFileInfo.sizeBytes:
                                raise ConsoleError(
                                    "file_integrity_error",
                                    "Downloaded content exceeds the expected size.",
                                )
                            checksumHasher.update(fileChunkBytes)
                            temporaryFile.write(fileChunkBytes)

                    if (
                        intDownloadedBytes != expectedFileInfo.sizeBytes
                        or checksumHasher.hexdigest() != expectedFileInfo.sha256
                    ):
                        raise ConsoleError(
                            "file_integrity_error",
                            "Downloaded content failed its size or SHA-256 check.",
                        )

                if overwrite:
                    os.replace(pathTemporary, pathDestination)
                else:
                    # Windows rename refuses an existing target, including one created during transfer.
                    os.rename(pathTemporary, pathDestination)
                return str(pathDestination)
            finally:
                pathTemporary.unlink(missing_ok=True)
        except BaseException:
            try:
                request_json(f"shared-files/downloads/{strTransferId}/cancel/", {})
            except Exception:
                # Preserve the original failure; Console expires unreachable downloads.
                pass
            raise

    return RetryBudget().run(_download_file)
