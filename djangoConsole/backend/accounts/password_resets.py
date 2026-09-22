# FileName: password_resets.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import hashlib
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import cast

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.views.decorators.debug import sensitive_variables

from console_project.config import LimitsConfig
from executors.session_state import revoke_user_executor_sessions
from notifications.models import EmailDelivery, EmailStatus, EmailType
from organizations.permissions import (
    get_current_membership,
    lock_account_for_password_reset,
)

from .api_keys import revoke_active_api_keys
from .models import PasswordResetRequest, User, UserManager
from .passwords import validate_new_password

_PASSWORD_RESET_TOKEN_LIFETIME = timedelta(hours=1)
_PASSWORD_RESET_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}")


@dataclass(frozen=True)
class PasswordResetLinkInfo:
    email: str
    expiresAt: datetime


@dataclass(frozen=True)
class PasswordResetTokenDeliveryInfo(PasswordResetLinkInfo):
    """Private worker data; the requesting HTTP client must never receive this secret."""

    token: str = field(repr=False)


def _build_invalid_password_reset_error() -> ValidationError:
    return ValidationError(
        "The password reset link is invalid or expired.",
        code="invalid_password_reset_token",
    )


@sensitive_variables()
def _get_password_reset_credential_hash(user: User, *, secret: str | None = None) -> str:
    # NOTE: Session revocation and profile edits do not invalidate this proof.
    return salted_hmac(
        "accounts.password_reset.credentials",
        f"{user.id}:{user.email}:{user.password}",
        secret=secret,
        algorithm="sha256",
    ).hexdigest()


@sensitive_variables()
def _has_current_reset_credentials(
    resetRequest: PasswordResetRequest, user: User
) -> bool:
    return (
        user.is_active
        and user.has_usable_password()
        and resetRequest.user_id == user.id
        and any(
            constant_time_compare(
                resetRequest.credential_hash,
                _get_password_reset_credential_hash(user, secret=secret),
            )
            for secret in [settings.SECRET_KEY, *settings.SECRET_KEY_FALLBACKS]
        )
    )


def _require_reset_token_unexpired(resetRequest: PasswordResetRequest) -> datetime:
    expiresAt = resetRequest.expires_at
    if (
        resetRequest.token_hash is None
        or expiresAt is None
        or expiresAt <= timezone.now()
    ):
        raise _build_invalid_password_reset_error()
    return expiresAt


@sensitive_variables()
def _get_password_reset_request(token: str) -> PasswordResetRequest:
    if _PASSWORD_RESET_TOKEN_PATTERN.fullmatch(token) is None:
        raise _build_invalid_password_reset_error()
    tokenHash = hashlib.sha256(token.encode("ascii")).hexdigest()
    try:
        return PasswordResetRequest.objects.select_related("user").get(
            token_hash=tokenHash
        )
    except PasswordResetRequest.DoesNotExist:
        raise _build_invalid_password_reset_error() from None


@sensitive_variables()
@transaction.atomic
def request_password_reset_email(email: str) -> None:
    """Queue recovery mail with a fixed account identity and no plaintext token.

    The HTTP adapter applies source limits and returns the same response for unknown,
    inactive, unusable-password, cooldown, and accepted addresses.
    """
    if settings.CONSOLE_URL is None:
        raise ImproperlyConfigured(
            "Configure consoleUrl, supportEmail, and smtp in Console.jsonc before requesting email."
        )
    delivery = EmailDelivery(
        email_type=EmailType.PASSWORD_RESET,
        recipient=UserManager.normalize_email(email),
    )
    delivery.full_clean(validate_unique=False, validate_constraints=False)
    userId = (
        User.objects.filter(email=delivery.recipient).values_list("id", flat=True).first()
    )
    if userId is None:
        return
    try:
        user = lock_account_for_password_reset(userId=userId)
    except PermissionDenied:
        return
    # The account may have changed its email while this request was waiting for its lock.
    if user.email != delivery.recipient or not user.has_usable_password():
        return

    previousDelivery = (
        EmailDelivery.objects
        .filter(email_type=EmailType.PASSWORD_RESET, recipient=delivery.recipient)
        .order_by("-created_at", "-id")
        .first()
    )
    requestedAt = timezone.now()
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    if previousDelivery is not None:
        if previousDelivery.status in (EmailStatus.PENDING, EmailStatus.SENDING):
            return
        cooldownStart = previousDelivery.attempted_at or previousDelivery.created_at
        if requestedAt < cooldownStart + timedelta(seconds=limits.emailResendSeconds):
            return

    # Never lock or update an earlier delivery while holding the account lock.
    # The worker takes delivery and dispatch locks before the organization and account.
    delivery.created_at = requestedAt
    delivery.save(force_insert=True)
    PasswordResetRequest.objects.update_or_create(
        user=user,
        defaults={
            "delivery": delivery,
            "credential_hash": _get_password_reset_credential_hash(user),
            "token_hash": None,
            "issued_at": None,
            "expires_at": None,
        },
    )


@sensitive_variables()
@transaction.atomic
def issue_password_reset_token(
    delivery: EmailDelivery,
) -> PasswordResetTokenDeliveryInfo | None:
    """Issue a token once while the worker holds this delivery's reservation transaction."""
    if delivery.email_type != EmailType.PASSWORD_RESET:
        raise ValueError("A password reset delivery is required.")
    userId = (
        PasswordResetRequest.objects
        .filter(delivery_id=delivery.id)
        .values_list("user_id", flat=True)
        .first()
    )
    if userId is None:
        return None
    try:
        user = lock_account_for_password_reset(userId=userId)
    except PermissionDenied:
        return None
    resetRequest = (
        PasswordResetRequest.objects
        .select_for_update()
        .filter(user_id=user.id, delivery_id=delivery.id)
        .first()
    )
    if (
        resetRequest is None
        or resetRequest.token_hash is not None
        or user.email != delivery.recipient
        or not _has_current_reset_credentials(resetRequest, user)
    ):
        return None

    token = secrets.token_urlsafe(32)
    issuedAt = timezone.now()
    resetRequest.token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
    resetRequest.issued_at = issuedAt
    resetRequest.expires_at = issuedAt + _PASSWORD_RESET_TOKEN_LIFETIME
    resetRequest.save(update_fields=["token_hash", "issued_at", "expires_at"])
    return PasswordResetTokenDeliveryInfo(
        email=user.email, expiresAt=resetRequest.expires_at, token=token
    )


@sensitive_variables()
def get_password_reset_info(token: str) -> PasswordResetLinkInfo:
    """Inspect a valid link without consuming it or changing any account or session."""
    resetRequest = _get_password_reset_request(token)
    user = cast(User, resetRequest.user)
    try:
        get_current_membership(actorId=user.id)
    except PermissionDenied:
        raise _build_invalid_password_reset_error() from None
    if not _has_current_reset_credentials(resetRequest, user):
        raise _build_invalid_password_reset_error()
    return PasswordResetLinkInfo(
        email=user.email, expiresAt=_require_reset_token_unexpired(resetRequest)
    )


@sensitive_variables()
@transaction.atomic
def complete_password_reset(*, token: str, newPassword: str) -> User:
    """Change the proof's account password and consume its request in one transaction."""
    resetRequest = _get_password_reset_request(token)
    try:
        user = lock_account_for_password_reset(userId=resetRequest.user_id)
        # Re-read after the account lock: a resend or another completion may have won.
        resetRequest = PasswordResetRequest.objects.select_for_update().get(
            pk=resetRequest.pk, user_id=user.id, token_hash=resetRequest.token_hash
        )
    except (PermissionDenied, PasswordResetRequest.DoesNotExist):
        raise _build_invalid_password_reset_error() from None
    if not _has_current_reset_credentials(resetRequest, user):
        raise _build_invalid_password_reset_error()
    _require_reset_token_unexpired(resetRequest)
    try:
        validate_new_password(newPassword, user)
    except ValidationError as e:
        raise ValidationError({"new_password": e.error_list}) from None

    user.set_password(newPassword)
    # Password hashing or a lock wait may have crossed the link's expiry boundary.
    _require_reset_token_unexpired(resetRequest)
    user.save(update_fields=["password"])
    revoke_active_api_keys(userId=user.id)
    revoke_user_executor_sessions(user.id)
    resetRequest.delete()
    # NOTE: Email-change proofs are bound to the old password hash and are now invalid.
    # TODO: Revoke Editor credentials when Editor authentication is implemented.
    return user
