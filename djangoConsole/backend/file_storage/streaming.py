# FileName: streaming.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import logging
import time
from typing import BinaryIO, Self

from asgiref.sync import sync_to_async

from .models import DownloadSession
from .services import release_download, renew_download

_LOGGER = logging.getLogger("console.file_storage")


class AsyncFileStream:
    def __init__(self, transfer: DownloadSession, handle: BinaryIO) -> None:
        self.transfer = transfer
        self.handle = handle
        self.closed = False
        self.renewedAt = time.monotonic()

    def read(self) -> bytes:
        if self.closed:
            return b""
        if time.monotonic() - self.renewedAt > 20:
            renew_download(self.transfer.pk, self.transfer.organization_id)
            self.renewedAt = time.monotonic()
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
            _LOGGER.exception("Could not release a download slot immediately.")

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> bytes:
        try:
            chunkData = await sync_to_async(self.read, thread_sensitive=True)()
            if chunkData:
                return chunkData
        except BaseException:
            await sync_to_async(self.close, thread_sensitive=True)()
            raise
        await sync_to_async(self.close, thread_sensitive=True)()
        raise StopAsyncIteration
