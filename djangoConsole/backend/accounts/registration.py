# FileName: registration.py
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
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from console_project.config import LimitsConfig
from notifications.models import EmailDelivery, EmailStatus, EmailType
from operations.policies import require_organization_creation_allowed
from organizations.creation import OrganizationCreationResult, create_organization_records

from .models import RegistrationToken, User, UserManager

_REGISTRATION_TOKEN_LIFETIME = timedelta(hours=1)
_REGISTRATION_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}")


@dataclass(frozen=True)
class RegistrationTokenDeliveryInfo:
    """Private mail-delivery data, never a response to the anonymous requesting client."""

    email: str
    token: str = field(repr=False)
    expiresAt: datetime


def _build_invalid_registration_token_error() -> ValidationError:
    return ValidationError(
        "The registration link is invalid or expired.", code="invalid_registration_token"
    )


def _require_registration_token_unexpired(registrationToken: RegistrationToken) -> None:
    if registrationToken.expires_at <= timezone.now():
        raise _build_invalid_registration_token_error()


@sensitive_variables()
def _get_registration_token(token: str, *, forUpdate: bool) -> RegistrationToken:
    if _REGISTRATION_TOKEN_PATTERN.fullmatch(token) is None:
        raise _build_invalid_registration_token_error()
    strTokenHash = hashlib.sha256(token.encode("ascii")).hexdigest()
    registrationTokenQuery = RegistrationToken.objects.all()
    if forUpdate:
        registrationTokenQuery = registrationTokenQuery.select_for_update()
    try:
        registrationToken = registrationTokenQuery.get(token_hash=strTokenHash)
    except RegistrationToken.DoesNotExist:
        raise _build_invalid_registration_token_error() from None
    # Check time after any lock wait, using the row already loaded for this operation.
    _require_registration_token_unexpired(registrationToken)
    return registrationToken


@sensitive_variables()
@transaction.atomic
def request_registration_email(email: str) -> None:
    """Queue a registration request without generating a token or contacting SMTP.

    The HTTP adapter must apply source-based request limits and give a generic response.
    The worker issues the token only when preparing the first delivery attempt.
    """
    if settings.CONSOLE_URL is None:
        raise ImproperlyConfigured(
            "Configure consoleUrl, supportEmail, and smtp in Console.jsonc before requesting email."
        )
    delivery = EmailDelivery(
        email_type=EmailType.ORGANIZATION_REGISTRATION,
        recipient=UserManager.normalize_email(email),
    )
    delivery.full_clean(validate_unique=False, validate_constraints=False)

    # The policy row serializes registration requests; recipient lookups do not take row locks.
    # A worker may already hold a delivery or token lock before checking the same policy.
    require_organization_creation_allowed()
    if User.objects.filter(email=delivery.recipient).exists():
        return

    previousDelivery = (
        EmailDelivery.objects
        .filter(email_type=delivery.email_type, recipient=delivery.recipient)
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

    # Start the request age after any policy lock wait; previous outcomes remain history.
    delivery.created_at = requestedAt
    delivery.save(force_insert=True)


@sensitive_variables()
@transaction.atomic
def issue_registration_token(email: str) -> RegistrationTokenDeliveryInfo | None:
    """Prepare a new token for delivery to the supplied email address.

    None suppresses delivery for an existing account or during the resend interval.
    The public response must not distinguish these cases or include the returned secret.
    The caller handles request limits and mail delivery after the transaction commits.
    """
    strToken = secrets.token_urlsafe(32)
    issuedAt = timezone.now()
    candidateToken = RegistrationToken(
        email=UserManager.normalize_email(email),
        token_hash=hashlib.sha256(strToken.encode("ascii")).hexdigest(),
        issued_at=issuedAt,
        expires_at=issuedAt + _REGISTRATION_TOKEN_LIFETIME,
    )
    candidateToken.full_clean(validate_unique=False, validate_constraints=False)

    # Issuance and completion both lock the email token before the instance policy.
    registrationToken, boolTokenCreated = (
        RegistrationToken.objects.select_for_update().get_or_create(
            email=candidateToken.email,
            defaults={
                "token_hash": candidateToken.token_hash,
                "issued_at": candidateToken.issued_at,
                "expires_at": candidateToken.expires_at,
            },
        )
    )
    require_organization_creation_allowed()
    if User.objects.filter(email=registrationToken.email).exists():
        registrationToken.delete()
        return None

    issuedAt = timezone.now()
    limits = cast(LimitsConfig, settings.CONSOLE_LIMITS)
    if not boolTokenCreated and issuedAt < registrationToken.issued_at + timedelta(
        seconds=limits.emailResendSeconds
    ):
        return None

    # Start the lifetime after lock waits; replacing the digest invalidates the old link.
    registrationToken.token_hash = candidateToken.token_hash
    registrationToken.issued_at = issuedAt
    registrationToken.expires_at = issuedAt + _REGISTRATION_TOKEN_LIFETIME
    registrationToken.save(update_fields=["token_hash", "issued_at", "expires_at"])
    return RegistrationTokenDeliveryInfo(
        email=registrationToken.email,
        token=strToken,
        expiresAt=registrationToken.expires_at,
    )


@sensitive_variables()
def get_registration_email(token: str) -> str:
    """Read the fixed registration email without consuming the token or creating an account."""
    return _get_registration_token(token, forUpdate=False).email


@sensitive_variables()
@transaction.atomic
def complete_organization_registration(
    *, token: str, password: str, organizationName: str, username: str = ""
) -> OrganizationCreationResult:
    """Create the organization and consume its email token in one transaction.

    The email comes only from the locked token record, never from the submitted form.
    Creation checks the current instance policy; success does not open a login session.
    """
    registrationToken = _get_registration_token(token, forUpdate=True)
    try:
        creationResult = create_organization_records(
            verifiedEmail=registrationToken.email,
            password=password,
            organizationName=organizationName,
            username=username,
        )
    except IntegrityError:
        # The creation service has rolled back its savepoint, so this lookup is safe.
        # An invitation or another registration may have claimed the email meanwhile.
        if User.objects.filter(email=registrationToken.email).exists():
            raise ValidationError(
                "This email address is already registered.",
                code="email_already_registered",
            ) from None
        raise

    # A policy lock wait or password hashing may have crossed the expiry boundary.
    _require_registration_token_unexpired(registrationToken)
    registrationToken.delete()
    return creationResult
