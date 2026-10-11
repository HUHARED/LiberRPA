# FileName: contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from console_project.contracts import JsonRequest, JsonResponsePayload


MAX_FILE_RESPONSE_BYTES = 2 * 1024 * 1024


type FileRequestUuid = Annotated[UUID, Field(strict=False)]
type FilePath = Annotated[str, Field(min_length=1, max_length=16384)]


class FileListRequest(JsonRequest):
    department_path: FilePath
    name: str = Field(default="", max_length=128)
    sort_by: Literal["name", "size", "uploaded_at"] = "uploaded_at"
    order: Literal["asc", "desc"] = "desc"
    page: int = Field(default=1, ge=1)


class FilePathRequest(JsonRequest):
    path: FilePath


class FileUploadRequest(FilePathRequest):
    request_id: FileRequestUuid
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern="^[0-9a-f]{64}$")
    overwrite: bool = False


class FileDeleteRequest(JsonRequest):
    request_id: FileRequestUuid
    paths: list[FilePath] = Field(min_length=1, max_length=100)


class EmptyFileRequest(JsonRequest):
    pass


class FileInfoResponse(JsonResponsePayload):
    path: str
    name: str
    department_path: str
    size_bytes: int
    sha256: str
    uploaded_by_name: str
    uploaded_at: datetime


class FileUsageResponse(JsonResponsePayload):
    used_bytes: int
    reserved_bytes: int
    pending_cleanup_bytes: int
    limit_bytes: int
    max_file_bytes: int


class FileListResponse(JsonResponsePayload):
    files: list[FileInfoResponse]
    department_path: str
    usage: FileUsageResponse
    page: int
    page_size: int
    total_count: int
    total_pages: int


class FileUploadResponse(JsonResponsePayload):
    upload_id: UUID
    state: Literal["receiving", "completed", "failed", "expired", "canceled"]
    offset: int
    size_bytes: int
    chunk_bytes: int
    expires_at: datetime
    file: FileInfoResponse | None


class FileDeleteResponse(JsonResponsePayload):
    request_id: UUID
    deleted_paths: list[str]
    missing_paths: list[str]
    deleted_count: int


class FileDownloadResponse(JsonResponsePayload):
    transfer_id: UUID
    expires_at: datetime
    file: FileInfoResponse
