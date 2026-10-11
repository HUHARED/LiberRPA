# FileName: constants.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from enum import StrEnum


# NOTE: User.__str__() needs up to 407 characters (150 username + 254 email + 3 separators); keep the existing 420-character capacity.
INT_DISPLAY_NAME_SNAPSHOT_MAX_LENGTH = 420

# Windows file and directory names are measured in UTF-16 code units.
INT_WINDOWS_NAME_MAX_LENGTH = 255

# Package and shared-file uploads use the same 4 MiB transport chunks.
INT_UPLOAD_CHUNK_BYTES = 4 * 1024 * 1024


class RunLogLevel(StrEnum):
    VERBOSE = "VERBOSE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
