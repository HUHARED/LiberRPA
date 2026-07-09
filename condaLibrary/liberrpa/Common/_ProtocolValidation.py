# FileName: _ProtocolValidation.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from typing import cast

from liberrpa.Common._TypedValue import DictSocketResult


def ensure_socket_result(value: object, source: str = "Socket.IO") -> DictSocketResult:
    if not isinstance(value, dict):
        raise ValueError(f"{source} returned an invalid socket result. Expected dict, got {type(value).__name__}.")

    expectedKeys = {"boolSuccess", "data"}
    if set(value) != expectedKeys:
        raise ValueError(
            f"{source} returned an invalid socket result. "
            f"Expected keys {sorted(expectedKeys)!r}, got {sorted(value.keys())!r}."
        )

    if not isinstance(value["boolSuccess"], bool):
        raise ValueError(
            f"{source} returned an invalid socket result. "
            f"'boolSuccess' should be bool, got {type(value['boolSuccess']).__name__}."
        )

    return cast(DictSocketResult, value)
