# FileName: _Lock.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from typing import Literal, TypedDict


class DictComponentManagementLock_File(TypedDict):
    """A Project or Repository operation lock file."""

    schemaVersion: Literal[1]

    ownerId: str
    processId: int
    processCreateTime: float

    operation: str
    createdAt: str
