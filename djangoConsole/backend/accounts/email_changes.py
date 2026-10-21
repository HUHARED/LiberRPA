# FileName: email_changes.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import hashlib
import json
import math
import re
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import cast

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import EmailField
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.views.decorators.debug import sensitive_variables

from console_project.config import LimitsConfig
from operations.contracts import AuditAction
from operations.audit import get_audit_snapshot, record_audit
from notifications.models import EmailDelivery, EmailType
from notifications.recipients import register_member_recipient
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
    get_current_membership,
    resolve_organization_access,
)

from .models import EmailChangeRequest, User, UserManager

_EMAIL_CHANGE_TOKEN_LIFETIME = timedelta(hours=1)
_EMAIL_CHANGE_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}")


class EmailChangeCooldownError(Exception):
    def __init__(self, retryAfterSeconds: int) -> None:
        self.retryAfterSeconds = retryAfterSeconds
        super().__init__("Wait before requesting another email change.")


@dataclass(frozen=True)
class EmailChangeLinkInfo:
    newEmail: str
    expiresAt: datetime


@dataclass(frozen=True)
class EmailChangeTokenDeliveryInfo(EmailChangeLinkInfo):
    """Private worker data; never return the secret to the initiating browser."""

    token: str = field(repr=False)


def _build_invalid_email_change_error() -> ValidationError:
    return ValidationError(
        "The email change link is invalid or expired.", code="invalid_email_change_token"
    )


def _build_email_unavailable_error() -> ValidationError:
    return ValidationError(
        "This email address is already registered.", code="email_already_registered"
    )


def _resolve_email_change_access(
    userId: uuid.UUID, *, forUpdate: bool
) -> OrganizationAccessContext:
    """Resolve current business eligibility; callers separately verify the password or proof."""
    membership = get_current_membership(actorId=userId)
    return resolve_organization_access(
        actorId=userId,
        organizationId=membership.organization_id,
        channel=AccessChannel.SESSION,
        forUpdate=forUpdate,
    )


@sensitive_variables()
def _get_email_change_credential_hash(
    user: User, newEmail: str, *, secret: str | None = None
) -> str:
    # Bind the exact destination and current credentials without tying the proof to a session.
    strAuthValue = json.dumps([str(user.id), user.email, user.password, newEmail])
    return salted_hmac(
        "accounts.email_change.credentials",
        strAuthValue,
        secret=secret,
        algorithm="sha256",
    ).hexdigest()


@sensitive_variables()
def _has_current_email_change_credentials(
    changeRequest: EmailChangeRequest, user: User
) -> bool:
    return (
        user.is_active
        and user.has_usable_password()
        and changeRequest.user_id == user.id
        and any(
            constant_time_compare(
                changeRequest.credential_hash,
                _get_email_change_credential_hash(
                    user, changeRequest.new_email, secret=strSecret
                ),
            )
            for strSecret in [settings.SECRET_KEY, *settings.SECRET_KEY_FALLBACKS]
        )
    )


def _require_email_change_token_unexpired(changeRequest: EmailChangeRequest) -> datetime:
    expiresAt = changeRequest.expires_at
    if (
        changeRequest.token_hash is None
        or changeRequest.confirmed_at is not None
        or expiresAt is None
        or expiresAt <= timezone.now()
    ):
        raise _build_invalid_email_change_error()
    return expiresAt


@sensitive_variables()
def _get_email_change_request(token: str) -> EmailChangeRequest:
    if _EMAIL_CHANGE_TOKEN_PATTERN.fullmatch(token) is None:
        raise _build_invalid_email_change_error()
    strTokenHash = hashlib.sha256(token.encode("ascii")).hexdigest()
    try:
        return EmailChangeRequest.objects.get(token_hash=strTokenHash)
    except EmailChangeRequest.DoesNotExist:
        raise _build_invalid_email_change_error() from None


@sensitive_variables()
def request_email_change(
    *,
    access: OrganizationAccessContext,
    currentPassword: str,
    newEmail: str,
) -> None:
    """Authorize and queue a new address while leaving the account's current email intact.

    The caller supplies rechecked access and owns the write transaction.
    """
    if access.channel != AccessChannel.SESSION:
        raise PermissionDenied("A signed-in account is required to change its email.")
    user = access.actor
    # A hash upgrade here would invalidate existing sessions, contrary to email-change semantics.
    if not check_password(currentPassword, user.password):
        raise ValidationError({"current_password": "The current password is incorrect."})

    newEmail = UserManager.normalize_email(newEmail)
    try:
        newEmailField = cast(
            "EmailField[str, str]", EmailChangeRequest._meta.get_field("new_email")
        )
        newEmailField.clean(newEmail, None)
    except ValidationError as e:
        raise ValidationError({"new_email": e.error_list}) from None
    if newEmail == user.email:
        raise ValidationError({"new_email": "Enter a different email address."})
    if User.objects.filter(email=newEmail).exists():
        raise _build_email_unavailable_error()

    # The account lock serializes this cursor; never lock old deliveries in this order.
    previousRequest = (
        EmailChangeRequest.objects.select_related("delivery").filter(user=user).first()
    )
    requestedAt = timezone.now()
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    if previousRequest is not None:
        cooldownStart = previousRequest.issued_at or previousRequest.delivery.created_at
        retryAt = cooldownStart + timedelta(seconds=limits.emailResendSeconds)
        if requestedAt < retryAt:
            raise EmailChangeCooldownError(
                max(1, math.ceil((retryAt - requestedAt).total_seconds()))
            )

    delivery = EmailDelivery.objects.create(
        organization_id=access.organization.id,
        organization_name=access.organization.name,
        email_type=EmailType.EMAIL_CHANGE_VERIFICATION,
        recipient=newEmail,
        created_at=requestedAt,
    )
    EmailChangeRequest.objects.update_or_create(
        user=user,
        defaults={
            "delivery": delivery,
            "new_email": newEmail,
            "credential_hash": _get_email_change_credential_hash(user, newEmail),
            "token_hash": None,
            "issued_at": None,
            "expires_at": None,
            "confirmed_at": None,
        },
    )
    record_audit(
        AuditAction.ACCOUNT_REQUEST_EMAIL_CHANGE,
        actor=user,
        organization=access.organization,
        target=user,
        channel=access.channel,
    )


@sensitive_variables()
@transaction.atomic
def issue_email_change_token(
    delivery: EmailDelivery,
) -> EmailChangeTokenDeliveryInfo | None:
    """Issue a token once inside the worker's delivery reservation transaction."""
    if delivery.email_type != EmailType.EMAIL_CHANGE_VERIFICATION:
        raise ValueError("An email change verification delivery is required.")
    userId = (
        EmailChangeRequest.objects
        .filter(delivery_id=delivery.id)
        .values_list("user_id", flat=True)
        .first()
    )
    if userId is None:
        return None
    try:
        access = _resolve_email_change_access(userId, forUpdate=True)
        user = access.actor
    except PermissionDenied:
        return None
    changeRequest = (
        EmailChangeRequest.objects
        .select_for_update()
        .filter(user_id=user.id, delivery_id=delivery.id)
        .first()
    )
    if (
        changeRequest is None
        or changeRequest.token_hash is not None
        or changeRequest.new_email != delivery.recipient
        or not _has_current_email_change_credentials(changeRequest, user)
        or User.objects.filter(email=changeRequest.new_email).exists()
    ):
        return None

    strToken = secrets.token_urlsafe(32)
    issuedAt = timezone.now()
    changeRequest.token_hash = hashlib.sha256(strToken.encode("ascii")).hexdigest()
    changeRequest.issued_at = issuedAt
    changeRequest.expires_at = issuedAt + _EMAIL_CHANGE_TOKEN_LIFETIME
    changeRequest.save(update_fields=["token_hash", "issued_at", "expires_at"])
    return EmailChangeTokenDeliveryInfo(
        newEmail=changeRequest.new_email,
        expiresAt=changeRequest.expires_at,
        token=strToken,
    )


@sensitive_variables()
def get_email_change_info(token: str) -> EmailChangeLinkInfo:
    """Read the fixed destination without changing the account or consuming the proof."""
    changeRequest = _get_email_change_request(token)
    try:
        access = _resolve_email_change_access(changeRequest.user_id, forUpdate=False)
        user = access.actor
    except PermissionDenied:
        raise _build_invalid_email_change_error() from None
    if not _has_current_email_change_credentials(changeRequest, user):
        raise _build_invalid_email_change_error()
    return EmailChangeLinkInfo(
        newEmail=changeRequest.new_email,
        expiresAt=_require_email_change_token_unexpired(changeRequest),
    )


@sensitive_variables()
@transaction.atomic
def confirm_email_change(token: str) -> None:
    """Change the proof's account email, consume its authorization, and queue the old-address notice."""
    changeRequest = _get_email_change_request(token)
    try:
        access = _resolve_email_change_access(changeRequest.user_id, forUpdate=True)
        user = access.actor
        changeRequest = EmailChangeRequest.objects.select_for_update().get(
            pk=changeRequest.pk, user_id=user.id, token_hash=changeRequest.token_hash
        )
    except (PermissionDenied, EmailChangeRequest.DoesNotExist):
        raise _build_invalid_email_change_error() from None
    if not _has_current_email_change_credentials(changeRequest, user):
        raise _build_invalid_email_change_error()
    expiresAt = _require_email_change_token_unexpired(changeRequest)
    if User.objects.filter(email=changeRequest.new_email).exists():
        raise _build_email_unavailable_error()

    strOldEmail = user.email
    dictAuditBefore = get_audit_snapshot(user)
    user.email = changeRequest.new_email
    try:
        # The savepoint keeps the outer transaction usable after a uniqueness race.
        with transaction.atomic():
            user.save(update_fields=["email"])
    except IntegrityError:
        if (
            User.objects
            .filter(email=changeRequest.new_email)
            .exclude(pk=user.id)
            .exists()
        ):
            raise _build_email_unavailable_error() from None
        raise

    register_member_recipient(access.organization.pk, user.email)

    confirmedAt = timezone.now()
    # A database uniqueness wait may have crossed expiry; roll back the account write too.
    if expiresAt <= confirmedAt:
        raise _build_invalid_email_change_error()
    changeRequest.confirmed_at = confirmedAt
    changeRequest.save(update_fields=["confirmed_at"])
    record_audit(
        AuditAction.ACCOUNT_CHANGE_EMAIL,
        actor=user,
        organization=access.organization,
        target=user,
        before=dictAuditBefore,
    )
    # Keep the consumed request as the per-account resend cursor, including across address changes.
    EmailDelivery.objects.create(
        organization_id=access.organization.id,
        organization_name=access.organization.name,
        email_type=EmailType.EMAIL_CHANGE_NOTICE,
        recipient=strOldEmail,
        created_at=confirmedAt,
    )
    # NOTE: The password and session version stay unchanged; existing sessions and independent keys remain valid.
    # Password reset requests bound to the old email become invalid automatically.
