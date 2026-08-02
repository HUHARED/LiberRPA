# FileName: _Hash.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"


from pathlib import Path
import base64
import hashlib


def calculate_file_sha256(filePath: Path) -> str:
    hashObj = hashlib.sha256()

    with filePath.open("rb") as fileObj:
        while chunk := fileObj.read(1024 * 1024):
            hashObj.update(chunk)

    return hashObj.hexdigest()


def calculate_record_hash(value: bytes) -> str:
    digest = hashlib.sha256(value).digest()
    strEncodedDigest = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return f"sha256={strEncodedDigest}"
