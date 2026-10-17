# FileName: urls.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.urls import path

from .http import session_file_view, api_file_view
from .views import (
    list_shared_files,
    query_shared_file,
    create_file_upload,
    get_file_upload,
    append_file_chunk,
    complete_file_upload,
    cancel_file_upload,
    delete_shared_files,
    create_file_download,
    cancel_file_download,
    download_file_content,
)

# The two credential boundaries share identical operations, not a string-based action dispatcher.
urlpatterns = [
    path(
        "shared-files/list/",
        session_file_view(list_shared_files),
        name="shared-files-list",
    ),
    path(
        "shared-files/query/",
        session_file_view(query_shared_file),
        name="shared-files-query",
    ),
    path(
        "shared-files/uploads/",
        session_file_view(create_file_upload),
        name="shared-files-upload",
    ),
    path(
        "shared-files/uploads/<uuid:uploadId>/",
        session_file_view(get_file_upload),
        name="shared-files-status",
    ),
    path(
        "shared-files/uploads/<uuid:uploadId>/chunks/<int:offset>/",
        session_file_view(append_file_chunk),
        name="shared-files-chunk",
    ),
    path(
        "shared-files/uploads/<uuid:uploadId>/complete/",
        session_file_view(complete_file_upload),
        name="shared-files-complete",
    ),
    path(
        "shared-files/uploads/<uuid:uploadId>/cancel/",
        session_file_view(cancel_file_upload),
        name="shared-files-cancel",
    ),
    path(
        "shared-files/deletion/",
        session_file_view(delete_shared_files),
        name="shared-files-delete",
    ),
    path(
        "shared-files/downloads/",
        session_file_view(create_file_download),
        name="shared-files-download",
    ),
    path(
        "shared-files/downloads/<uuid:transferId>/cancel/",
        session_file_view(cancel_file_download),
        name="shared-files-cancel-download",
    ),
    path(
        "shared-files/downloads/<uuid:transferId>/",
        session_file_view(download_file_content),
        name="shared-files-content",
    ),
    path(
        "v1/shared-files/list/",
        api_file_view(list_shared_files),
        name="public-shared-files-list",
    ),
    path(
        "v1/shared-files/query/",
        api_file_view(query_shared_file),
        name="public-shared-files-query",
    ),
    path(
        "v1/shared-files/uploads/",
        api_file_view(create_file_upload),
        name="public-shared-files-upload",
    ),
    path(
        "v1/shared-files/uploads/<uuid:uploadId>/",
        api_file_view(get_file_upload),
        name="public-shared-files-status",
    ),
    path(
        "v1/shared-files/uploads/<uuid:uploadId>/chunks/<int:offset>/",
        api_file_view(append_file_chunk),
        name="public-shared-files-chunk",
    ),
    path(
        "v1/shared-files/uploads/<uuid:uploadId>/complete/",
        api_file_view(complete_file_upload),
        name="public-shared-files-complete",
    ),
    path(
        "v1/shared-files/uploads/<uuid:uploadId>/cancel/",
        api_file_view(cancel_file_upload),
        name="public-shared-files-cancel",
    ),
    path(
        "v1/shared-files/deletion/",
        api_file_view(delete_shared_files),
        name="public-shared-files-delete",
    ),
    path(
        "v1/shared-files/downloads/",
        api_file_view(create_file_download),
        name="public-shared-files-download",
    ),
    path(
        "v1/shared-files/downloads/<uuid:transferId>/cancel/",
        api_file_view(cancel_file_download),
        name="public-shared-files-cancel-download",
    ),
    path(
        "v1/shared-files/downloads/<uuid:transferId>/",
        api_file_view(download_file_content),
        name="public-shared-files-content",
    ),
]
