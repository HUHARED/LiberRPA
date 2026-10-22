# FileName: http.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import hashlib
import uuid

from django.http import HttpRequest

from accounts.resource_authentication import (
    ResourceAuthenticationContext,
    lock_resource_write_access,
)
from console_project.constants import INT_UPLOAD_CHUNK_BYTES
from organizations.http import lock_request_write_access
from organizations.models import Membership
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
    build_organization_access,
)

from .services import FileOperationError


type FileAuthentication = Membership | ResourceAuthenticationContext


class FileRequestError(Exception):
    """Malformed HTTP parameters, not an internal response or persistence error."""


def get_file_access(authentication: FileAuthentication) -> OrganizationAccessContext:
    if not isinstance(authentication, Membership):
        return authentication.access
    return build_organization_access(authentication, channel=AccessChannel.SESSION)


def get_file_api_key_id(authentication: FileAuthentication) -> uuid.UUID | None:
    return None if isinstance(authentication, Membership) else authentication.apiKeyId


def lock_file_access(
    request: HttpRequest, authentication: FileAuthentication
) -> OrganizationAccessContext:
    if not isinstance(authentication, Membership):
        return lock_resource_write_access(authentication)
    return lock_request_write_access(request, authentication)


def require_no_query_parameters(request: HttpRequest) -> None:
    if request.GET:
        raise FileRequestError("Use the request body; query parameters are not accepted.")


def parse_upload_chunk(request: HttpRequest) -> tuple[bytes, str]:
    require_no_query_parameters(request)
    if request.content_type != "application/octet-stream":
        raise FileOperationError(
            "invalid_chunk_type", "Send application/octet-stream content.", 415
        )
    chunkData = request.read(INT_UPLOAD_CHUNK_BYTES + 1)
    if not chunkData or len(chunkData) > INT_UPLOAD_CHUNK_BYTES:
        raise FileOperationError(
            "invalid_chunk_size", "Send a non-empty chunk of at most 4 MiB.", 400
        )
    strChunkSha256 = hashlib.sha256(chunkData).hexdigest()
    if strChunkSha256 != request.headers.get("X-Chunk-SHA256", ""):
        raise FileOperationError(
            "chunk_checksum_mismatch",
            "The chunk checksum does not match its content.",
            400,
        )
    return chunkData, strChunkSha256
