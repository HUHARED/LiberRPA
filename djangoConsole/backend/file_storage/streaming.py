# FileName: streaming.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging
import time
from typing import BinaryIO, Self

from .models import DownloadSession

from asgiref.sync import sync_to_async

from .services import release_download, renew_download

logger = logging.getLogger(__name__)


class _FileStream:
    def __init__(self, transfer: DownloadSession, handle: BinaryIO) -> None:
        self.transfer = transfer
        self.handle = handle
        self.closed = False
        self.renewed_at = time.monotonic()

    def read(self) -> bytes:
        if self.closed:
            return b""
        if time.monotonic() - self.renewed_at > 20:
            renew_download(self.transfer.pk, self.transfer.organization_id)
            self.renewed_at = time.monotonic()
        return self.handle.read(64 * 1024)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.handle.close()
        try:
            release_download(self.transfer.pk, self.transfer.organization_id)
        except Exception:
            # An expired lease is also reclaimed by cleanup_file_storage.
            logger.exception("Could not release a download slot immediately.")


class SyncFileStream(_FileStream):
    def __iter__(self) -> Self:
        return self

    def __next__(self) -> bytes:
        try:
            data = self.read()
            if data:
                return data
        except Exception:
            self.close()
            raise
        self.close()
        raise StopIteration


class AsyncFileStream(_FileStream):
    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> bytes:
        try:
            data = await sync_to_async(self.read, thread_sensitive=True)()
            if data:
                return data
        except BaseException:
            await sync_to_async(self.close, thread_sensitive=True)()
            raise
        await sync_to_async(self.close, thread_sensitive=True)()
        raise StopAsyncIteration
