# FileName: Console.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from liberrpa.Common import _Initialization  # noqa: F401 - Freeze the host identity before any resource request.

from typing import get_args
from uuid import UUID, uuid4

from liberrpa.Logging import Log
from liberrpa.Common._TypedValue import JsonValue, StrPath
from liberrpa.Common._ConsoleHttp import (
    ConsoleError as ConsoleError,
    RetryBudget,
    request_json,
)
from liberrpa.Common._Console import (
    DataQueueItemFilterStatus,
    DataQueueItemOrder,
    SharedFileSort,
    SortOrder,
    _DataQueueMutationOperation,
    Credential,
    DataQueueItem,
    DataQueuePage,
    DataQueueMutationResult,
    DataQueueClaimReplayError as DataQueueClaimReplayError,
    SharedFileInfo,
    SharedFileUsage,
    SharedFilePage,
    SharedFileDeleteResult,
    _validate_choice,
    _validate_batch_items,
    _parse_data_queue_selection,
    _normalize_queue_item_ids,
    _parse_data_queue_item_details,
    _mutate_data_queue_items,
    _upload_data_queue_items,
    _parse_shared_file_info,
    _upload_shared_file,
    _download_shared_file,
)


@Log.trace()
def asset_get_value(path: str) -> JsonValue:
    """
    Read the current value of an ordinary Console Asset.

    Parameters:
        path: The full Asset path, including its department path and name.

    Returns:
        JsonValue: The Asset value as a Python JSON value.
    """
    return request_json(
        "assets/get_value/",
        {"path": path},
        retryBudget=RetryBudget(),
    )["value"]


@Log.trace()
def asset_set_value(path: str, value: JsonValue) -> None:
    """
    Replace the value of an ordinary Console Asset.

    The value must match the Asset's existing type. Secret Text and Credential Assets must be maintained in Console.

    Writes are not retried automatically. A connection failure may leave the result uncertain; check Console before writing again.

    Parameters:
        path: The full Asset path, including its department path and name.
        value: The replacement value. Only JSON-compatible values are accepted.
    """
    request_json(
        "assets/set_value/",
        {"path": path, "value": value},
        isMutation=True,
    )


@Log.trace()
def asset_get_secret_text(path: str) -> str:
    """
    Read a Secret Text Asset using the host account's current permissions.

    The returned value is sensitive and should not be written to logs.

    Parameters:
        path: The full Asset path, including its department path and name.

    Returns:
        str: The decrypted secret text.
    """
    return request_json(
        "assets/get_secret_text/",
        {"path": path},
        retryBudget=RetryBudget(),
    )["value"]


@Log.trace()
def asset_get_credential(path: str) -> Credential:
    """
    Read a Credential Asset using the host account's current permissions.

    The returned username and password are sensitive and should not be written to logs.

    Parameters:
        path: The full Asset path, including its department path and name.

    Returns:
        Credential: The decrypted username and password.
    """
    dictCredential = request_json(
        "assets/get_credential/",
        {"path": path},
        retryBudget=RetryBudget(),
    )
    return Credential(
        username=dictCredential["username"],
        password=dictCredential["password"],
    )


@Log.trace()
def data_queue_query_items(
    queuePath: str,
    *,
    status: DataQueueItemFilterStatus = "all",
    order: DataQueueItemOrder = "oldest_first",
    itemId: str | None = None,
    count: int = 50,
    afterSequence: int | None = None,
) -> DataQueuePage:
    """
    Query Data Queue items without claiming them.

    Results may contain fewer than count items because each response is limited to 2 MiB. Continue with nextAfterSequence as afterSequence, keeping the same filters and order. Results may change between pages.

    Parameters:
        queuePath: The full Data Queue path, including its department path and name.
        status: The status filter: 'all', 'unclaimed', or 'claimed'.
        order: The item selection order: 'oldest_first' or 'newest_first'.
        itemId: An optional item UUID used to narrow the query.
        count: The maximum number of items to return, from 1 to 100.
        afterSequence: The previous result's nextAfterSequence, or None for the first page.

    Returns:
        DataQueuePage: The matching items and nextAfterSequence. A nextAfterSequence of None means there is no further page.
    """
    if afterSequence is not None and (
        type(afterSequence) is not int or afterSequence < 0
    ):
        raise ValueError("afterSequence must be a nonnegative integer or None.")
    dictResponse = request_json(
        "data-queues/query/",
        {
            "queue_path": queuePath,
            **_parse_data_queue_selection(status, order, count),
            "item_id": str(UUID(itemId)) if itemId is not None else None,
            "after_sequence": afterSequence,
        },
        retryBudget=RetryBudget(),
    )
    return DataQueuePage(
        items=[
            _parse_data_queue_item_details(dictItem) for dictItem in dictResponse["items"]
        ],
        nextAfterSequence=dictResponse["next_after_sequence"],
    )


@Log.trace()
def data_queue_upload_items(
    queuePath: str, items: list[JsonValue]
) -> DataQueueMutationResult:
    """
    Add a batch of JSON values to a Data Queue.

    Each item is limited to 1 MiB of UTF-8 JSON, and the complete request is limited to 2 MiB. Console may configure a smaller item limit. Invalid or oversized batches are rejected in full.

    If a network error leaves the result uncertain, check Console before uploading the same items again to avoid duplicates.

    Parameters:
        queuePath: The full Data Queue path, including its department path and name.
        items: A list containing 1 to 100 JSON values. To upload a JSON array as one item, wrap that array in an outer list.

    Returns:
        DataQueueMutationResult: The IDs of the added items.
    """
    return _upload_data_queue_items(queuePath=queuePath, items=items)


@Log.trace()
def data_queue_claim_items(
    queuePath: str,
    *,
    count: int = 1,
    status: DataQueueItemFilterStatus = "unclaimed",
    order: DataQueueItemOrder = "oldest_first",
    itemId: str | None = None,
) -> list[DataQueueItem]:
    """
    Mark matching Data Queue items as Claimed and return their data.

    The number of items claimed may be lower than count because each response is limited to 2 MiB. Choosing 'claimed' or 'all' allows previously claimed items to be selected again.

    If a network error leaves the result uncertain, check Console before calling again; another call may claim a different batch.

    Parameters:
        queuePath: The full Data Queue path, including its department path and name.
        count: The maximum number of items to claim, from 1 to 100.
        status: The status filter: 'unclaimed', 'claimed', or 'all'.
        order: The item selection order: 'oldest_first' or 'newest_first'.
        itemId: An optional item UUID used to narrow the selection.

    Returns:
        list[DataQueueItem]: The claimed item IDs and data. Returns an empty list when no items match.
    """
    claimResult = _mutate_data_queue_items(
        _DataQueueMutationOperation.CLAIM,
        queuePath,
        {
            **_parse_data_queue_selection(status, order, count),
            "item_id": str(UUID(itemId)) if itemId is not None else None,
        },
    )
    if claimResult.missingIds:
        raise DataQueueClaimReplayError(claimResult)
    return claimResult.items


@Log.trace()
def data_queue_reset_items(
    queuePath: str, itemIds: str | list[str]
) -> DataQueueMutationResult:
    """
    Reset selected Data Queue items to Unclaimed.

    Item IDs, data, original queue order, and the last claimant's identity and time are preserved.

    Parameters:
        queuePath: The full Data Queue path, including its department path and name.
        itemIds: One item UUID or a list containing 1 to 100 item UUIDs.

    Returns:
        DataQueueMutationResult: The reset, missing, and skipped item IDs.
    """
    return _mutate_data_queue_items(
        _DataQueueMutationOperation.RESET,
        queuePath,
        {"item_ids": _normalize_queue_item_ids(itemIds)},
    )


@Log.trace()
def data_queue_delete_items(
    queuePath: str,
    itemIds: str | list[str] | None = None,
    *,
    status: DataQueueItemFilterStatus | None = None,
    order: DataQueueItemOrder | None = None,
    count: int | None = None,
) -> DataQueueMutationResult:
    """
    Delete Data Queue items by ID or by status, order, and count.

    Supply itemIds or selection parameters, but not both. Prefer IDs from the items actually processed. Without IDs, status and count are required; order defaults to oldest-first.

    If a network error leaves the result uncertain, check Console before deleting by conditions again; another call may delete a different batch.

    Parameters:
        queuePath: The full Data Queue path, including its department path and name.
        itemIds: One item UUID or a list containing 1 to 100 item UUIDs. Leave as None to use selection parameters.
        status: The selection status: 'all', 'unclaimed', or 'claimed'. Required when itemIds is None.
        order: The selection order: 'oldest_first' or 'newest_first'. None uses 'oldest_first'.
        count: The maximum number to delete, from 1 to 100. Required when itemIds is None.

    Returns:
        DataQueueMutationResult: The deleted, missing, and skipped item IDs.
    """
    if itemIds is not None:
        if status is not None or order is not None or count is not None:
            raise ValueError("Choose itemIds or status/order/count, not both.")
        dictSelection: dict[str, object] = {
            "item_ids": _normalize_queue_item_ids(itemIds)
        }
    else:
        if status is None or count is None:
            raise ValueError("Specify status and count when deleting without itemIds.")
        dictSelection = _parse_data_queue_selection(
            status,
            order if order is not None else "oldest_first",
            count,
        )
    return _mutate_data_queue_items(
        _DataQueueMutationOperation.DELETE_ITEMS, queuePath, dictSelection
    )


@Log.trace()
def shared_file_list(
    departmentPath: str | None = None,
    *,
    name: str = "",
    sortBy: SharedFileSort = "uploaded_at",
    order: SortOrder = "desc",
    page: int = 1,
) -> SharedFilePage:
    """
    List one page of Shared Files from authorized Console departments.

    Each call returns one page. Console determines the page size, available as pageSize.

    Parameters:
        departmentPath: An optional full department path. None includes all authorized departments.
        name: An optional filename search filter. An empty string includes all names.
        sortBy: The sort field: 'name', 'size', or 'uploaded_at'.
        order: The sort direction: 'asc' or 'desc'.
        page: The page number, starting from 1.

    Returns:
        SharedFilePage: The file metadata, selected department (None when unfiltered), organization storage usage, and pagination details.
    """
    _validate_choice(sortBy, get_args(SharedFileSort.__value__), "sortBy")
    _validate_choice(order, get_args(SortOrder.__value__), "order")
    if type(page) is not int or page < 1:
        raise ValueError("page must be a positive integer.")
    dictResponse = request_json(
        "shared-files/list/",
        {
            "department_path": departmentPath,
            "name": name,
            "sort_by": sortBy,
            "order": order,
            "page": page,
        },
        retryBudget=RetryBudget(),
    )
    dictUsage = dictResponse["usage"]
    return SharedFilePage(
        files=[_parse_shared_file_info(dictFile) for dictFile in dictResponse["files"]],
        departmentPath=dictResponse["department_path"],
        usage=SharedFileUsage(
            usedBytes=dictUsage["used_bytes"],
            reservedBytes=dictUsage["reserved_bytes"],
            pendingCleanupBytes=dictUsage["pending_cleanup_bytes"],
            limitBytes=dictUsage["limit_bytes"],
            maxFileBytes=dictUsage["max_file_bytes"],
        ),
        page=dictResponse["page"],
        pageSize=dictResponse["page_size"],
        totalCount=dictResponse["total_count"],
        totalPages=dictResponse["total_pages"],
    )


@Log.trace()
def shared_file_get_info(path: str) -> SharedFileInfo:
    """
    Read current Shared File metadata without downloading its content.

    Parameters:
        path: The full Shared File path, including its department path and filename.

    Returns:
        SharedFileInfo: The file path, size, checksum, and upload details.
    """
    return _parse_shared_file_info(
        request_json("shared-files/query/", {"path": path}, retryBudget=RetryBudget())
    )


@Log.trace()
def shared_file_upload(
    localPath: StrPath,
    path: str,
    *,
    overwrite: bool = False,
) -> SharedFileInfo:
    """
    Upload a local file to Console as a Shared File.

    The file size is limited to 20 MiB. An existing Shared File is replaced only after the complete upload succeeds.

    Parameters:
        localPath: The local source file path. Accepts str or PathLike[str].
        path: The full target Shared File path, including its department path and filename.
        overwrite: If True, replaces an existing Shared File. If False, an existing file causes an error.

    Returns:
        SharedFileInfo: The published file metadata.
    """
    return _upload_shared_file(localPath=localPath, path=path, overwrite=overwrite)


@Log.trace()
def shared_file_download(
    path: str,
    folderPath: StrPath,
    *,
    filename: str | None = None,
    overwrite: bool = False,
) -> str:
    """
    Download a Shared File to a local folder.

    Missing folders are created automatically. The filename is sanitized for local use, with a Warning log if it changes. Existing files are preserved if downloading or verification fails.

    Parameters:
        path: The full Shared File path, including its department path and filename.
        folderPath: The destination folder. Accepts str or PathLike[str].
        filename: An optional local filename. None uses the filename returned by Console.
        overwrite: If True, replaces an existing file after verification. If False, a file at the sanitized destination causes FileExistsError.

    Returns:
        str: The actual absolute path of the downloaded file, including its sanitized filename.
    """
    return _download_shared_file(
        path=path,
        folderPath=folderPath,
        filename=filename,
        overwrite=overwrite,
    )


@Log.trace()
def shared_file_delete(paths: str | list[str]) -> SharedFileDeleteResult:
    """
    Delete Shared Files at the specified paths as one operation.

    Parameters:
        paths: One full Shared File path or a list containing 1 to 100 paths.

    Returns:
        SharedFileDeleteResult: The deleted and missing paths, and the number of deleted files.
    """
    listFilePath = [paths] if isinstance(paths, str) else paths
    _validate_batch_items(listFilePath)
    strRequestId = str(uuid4())
    dictDeletion = request_json(
        "shared-files/deletion/",
        {
            "request_id": strRequestId,
            "paths": listFilePath,
        },
        retryBudget=RetryBudget(),
        requestId=strRequestId,
    )
    return SharedFileDeleteResult(
        requestId=dictDeletion["request_id"],
        deletedPaths=dictDeletion["deleted_paths"],
        missingPaths=dictDeletion["missing_paths"],
        deletedCount=dictDeletion["deleted_count"],
    )
