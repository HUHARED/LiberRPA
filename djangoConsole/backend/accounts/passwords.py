# FileName: passwords.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

_INT_MIN_PASSWORD_LENGTH = 15
_INT_MAX_PASSWORD_LENGTH = 128


def validate_new_password(password: str, user: AbstractBaseUser) -> None:
    """Validate a proposed new password without changing its text or saving the user."""
    intPasswordLength = len(password)
    if intPasswordLength < _INT_MIN_PASSWORD_LENGTH:
        raise ValidationError(
            "The password must contain at least %(min_length)d characters.",
            code="password_too_short",
            params={"min_length": _INT_MIN_PASSWORD_LENGTH},
        )
    if intPasswordLength > _INT_MAX_PASSWORD_LENGTH:
        raise ValidationError(
            "The password must contain at most %(max_length)d characters.",
            code="password_too_long",
            params={"max_length": _INT_MAX_PASSWORD_LENGTH},
        )
    if password.isspace():
        raise ValidationError(
            "The password must not consist only of whitespace.",
            code="password_only_whitespace",
        )

    # Reuse the configured checks after rejecting invalid lengths.
    validate_password(password, user=user)
