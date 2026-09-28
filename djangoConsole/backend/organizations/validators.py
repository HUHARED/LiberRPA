# FileName: validators.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import unicodedata

from django.core.exceptions import ValidationError


def validate_path_segment(segmentName: str) -> None:
    """Validate one logical path name without modifying the supplied text."""
    if not segmentName:
        raise ValidationError("The name must not be empty.", code="invalid_path_segment")
    if segmentName != segmentName.strip():
        raise ValidationError(
            "The name must not start or end with whitespace.",
            code="invalid_path_segment",
        )
    # This also rejects the standalone '.' and '..' path segments.
    if segmentName.endswith("."):
        raise ValidationError(
            "The name must not end with a period.", code="invalid_path_segment"
        )
    if any(
        char in "/\\" or unicodedata.category(char) in {"Cc", "Cs"}
        for char in segmentName
    ):
        raise ValidationError(
            "The name must not contain path separators, control characters, or surrogate code points.",
            code="invalid_path_segment",
        )


def path_name_key(value: str) -> str:
    """Build the canonical caseless key without changing the display name."""
    # NOTE: Persisted name keys and request digests use this rule; changes require an explicit data migration.
    return unicodedata.normalize("NFD", unicodedata.normalize("NFD", value).casefold())


def normalize_path_name(value: str) -> str:
    validate_path_segment(value)
    if len(value) > 128:
        raise ValidationError("Use at most 128 valid Unicode characters.")
    normalized = unicodedata.normalize("NFC", value)
    if len(normalized) > 128:
        raise ValidationError("The normalized name exceeds 128 characters.")
    return normalized
