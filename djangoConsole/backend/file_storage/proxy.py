# FileName: proxy.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging
import socket
import uuid
from dataclasses import dataclass
from datetime import datetime

from django.conf import settings
from django.utils import timezone

_LOGGER = logging.getLogger("console.file_storage")


@dataclass(frozen=True)
class DownloadProxySnapshot:
    capturedAt: datetime
    activeIds: frozenset[uuid.UUID]


def get_download_proxy_snapshot() -> DownloadProxySnapshot | None:
    """Read active HTTP downloads before acquiring any database locks."""
    from .services import FileOperationError

    proxyConfig = settings.CONSOLE_FILE_TRANSFER_PROXY
    if proxyConfig is None:
        return None

    capturedAt = timezone.now()
    activeIds: set[uuid.UUID] = set()
    try:
        with socket.create_connection(
            (proxyConfig.host, proxyConfig.port), timeout=2
        ) as connection:
            connection.sendall(b"show table download_transfers data.conn_cur gt 0\n")
            with connection.makefile("r", encoding="ascii") as response:
                if not response.readline().startswith("# table: download_transfers,"):
                    raise ValueError("The download tracking table is unavailable.")
                for line in response:
                    if not line.strip():
                        break
                    fields = dict(
                        part.split("=", 1) for part in line.split() if "=" in part
                    )
                    if int(fields["conn_cur"]) > 0:
                        activeIds.add(uuid.UUID(fields["key"]))
                else:
                    raise ValueError("The download tracking response is incomplete.")
    except (OSError, ValueError, KeyError, UnicodeError):
        _LOGGER.exception("Could not read active downloads from the transfer proxy.")
        raise FileOperationError(
            "transfer_proxy_unavailable",
            "File downloads are temporarily unavailable. Please try again later.",
            503,
        ) from None
    return DownloadProxySnapshot(capturedAt, frozenset(activeIds))
