# FileName: models.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.core.validators import (
    MaxLengthValidator,
    ProhibitNullCharactersValidator,
    RegexValidator,
)
from django.db import models
from django.db.models.functions import Lower, Trim
from django.utils import timezone
from django.utils.crypto import salted_hmac

from console_project.validators import validate_time_zone

from .passwords import validate_new_password

STR_PLATFORM_ADMIN_LOGIN = "admin"


class UserManager(BaseUserManager["User"]):
    @classmethod
    def normalize_login(cls, login: str) -> str:
        # Normalize both identifier formats without combining their account namespaces.
        return AbstractBaseUser.normalize_username(login).strip().lower()

    @classmethod
    def normalize_email(cls, email: str) -> str:
        return cls.normalize_login(email)

    def get_by_natural_key(self, username: str) -> "User":
        # Django calls the login identifier "username", regardless of its account field.
        return self.get(email=self.normalize_email(username), is_platform_admin=False)

    async def aget_by_natural_key(self, username: str) -> "User":
        return await self.aget(
            email=self.normalize_email(username), is_platform_admin=False
        )

    def create_user(
        self,
        email: str,
        password: str | None = None,
        *,
        username: str,
        time_zone: str = "UTC",
    ) -> "User":
        """Create an account record; callers handle verified registration and membership."""
        strEmail = self.normalize_email(email)
        if not strEmail:
            raise ValidationError({"email": "An email address is required."})
        user = self.model(
            email=strEmail,
            username=username.strip(),
            time_zone=time_zone,
        )
        # Validate fields once. The database enforces uniqueness at the actual write.
        user.full_clean(
            exclude=["password"], validate_unique=False, validate_constraints=False
        )
        if password is not None:
            validate_new_password(password, user)
        # None deliberately creates an unusable password, following Django's API.
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(AbstractBaseUser):
    """Account identity; organization and department permissions are separate."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, blank=True, default="")
    platform_login = models.CharField(
        max_length=254,
        blank=True,
        default="",
        validators=[
            RegexValidator(r"^[^\x00-\x1f\x7f-\x9f]+$", "Enter a single-line login name.")
        ],
    )
    username = models.CharField(
        max_length=150, validators=[ProhibitNullCharactersValidator()]
    )
    time_zone = models.CharField(
        max_length=100, default="UTC", validators=[validate_time_zone]
    )
    is_active = models.BooleanField(default=True)
    is_platform_admin = models.BooleanField(default=False)
    session_version = models.PositiveBigIntegerField(default=0, editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(email=Lower(Trim("email"))),
                name="accounts_user_email_canonical",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    is_platform_admin=True,
                    email="",
                    platform_login=STR_PLATFORM_ADMIN_LOGIN,
                )
                | (
                    models.Q(is_platform_admin=False, platform_login="")
                    & ~models.Q(email="")
                ),
                name="accounts_user_identity_valid",
            ),
            models.UniqueConstraint(
                fields=["is_platform_admin"],
                condition=models.Q(is_platform_admin=True),
                name="accounts_one_platform_admin",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.username} ({self.platform_login or self.email})"

    def _get_session_auth_hash(self, secret: str | None = None) -> str:
        """Include the revocation version in Django's normal and fallback session hashes."""
        strKeySalt = "accounts.User.get_session_auth_hash"
        strAuthValue = f"{self.password}:{self.session_version}"
        return salted_hmac(
            strKeySalt,
            strAuthValue,
            secret=secret,
            algorithm="sha256",
        ).hexdigest()


class EditorSession(models.Model):
    """An independent native Editor login bound to current account authentication."""

    user_id: uuid.UUID
    organization_id: uuid.UUID

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="editor_sessions"
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="editor_sessions",
    )
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    auth_hash = models.CharField(max_length=64, editable=False)
    computer_name = models.CharField(
        max_length=128,
        validators=[
            RegexValidator(
                r"^[^\x00-\x1f\x7f-\x9f]+$", "Use a single-line computer name."
            )
        ],
    )
    client_version = models.CharField(
        max_length=64,
        validators=[
            RegexValidator(
                r"^[^\x00-\x1f\x7f-\x9f]+$", "Use a single-line client version."
            )
        ],
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    last_seen_at = models.DateTimeField(editable=False)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(last_seen_at__gte=models.F("created_at"))
                & models.Q(expires_at__gt=models.F("last_seen_at")),
                name="editor_session_timestamps_valid",
            ),
        ]


class ApiKey(models.Model):
    """Independent account credential; permissions are resolved from current membership."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id: uuid.UUID
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="api_keys")
    name = models.CharField(
        max_length=100,
        validators=[RegexValidator(r"^[^\x00-\x1f\x7f]+$", "Enter a single-line name.")],
    )
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    notes = models.TextField(
        blank=True,
        default="",
        validators=[MaxLengthValidator(2000), ProhibitNullCharactersValidator()],
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    expires_at = models.DateTimeField(db_index=True)
    last_used_at = models.DateTimeField(null=True, blank=True, editable=False)
    revoked_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        indexes = [
            models.Index(fields=["user", "expires_at"], name="api_key_user_expiry_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(expires_at__gt=models.F("created_at")),
                name="api_key_expiry_after_creation",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class RegistrationToken(models.Model):
    """One current email token for creating a new organization; consumed tokens are deleted."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    issued_at = models.DateTimeField(editable=False)
    expires_at = models.DateTimeField(db_index=True, editable=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(email=Lower(Trim("email"))) & ~models.Q(email=""),
                name="registration_token_email_canonical",
            ),
            models.CheckConstraint(
                condition=models.Q(expires_at__gt=models.F("issued_at")),
                name="registration_token_expiry_after_issue",
                violation_error_message="A registration token must expire after it was issued.",
            ),
        ]

    def __str__(self) -> str:
        return f"Organization registration for {self.email}"


class PasswordResetRequest(models.Model):
    """One current reset request per account; only the worker issues its secret token."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id: uuid.UUID
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="+")
    delivery_id: uuid.UUID
    delivery = models.OneToOneField(
        "notifications.EmailDelivery", on_delete=models.CASCADE, related_name="+"
    )
    # Bind queued mail and issued proofs to the account's current email and password.
    credential_hash = models.CharField(max_length=64, editable=False)
    token_hash = models.CharField(
        max_length=64, unique=True, null=True, blank=True, editable=False
    )
    issued_at = models.DateTimeField(null=True, blank=True, editable=False)
    expires_at = models.DateTimeField(
        null=True, blank=True, db_index=True, editable=False
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        token_hash__isnull=True,
                        issued_at__isnull=True,
                        expires_at__isnull=True,
                    )
                    | (
                        models.Q(
                            token_hash__isnull=False,
                            issued_at__isnull=False,
                            expires_at__isnull=False,
                            expires_at__gt=models.F("issued_at"),
                        )
                        & ~models.Q(token_hash="")
                    )
                ),
                name="password_reset_proof_state_valid",
            ),
        ]


class EmailChangeRequest(models.Model):
    """The latest email-change authorization and resend history for one account."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id: uuid.UUID
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="+")
    delivery_id: uuid.UUID
    delivery = models.OneToOneField(
        "notifications.EmailDelivery", on_delete=models.CASCADE, related_name="+"
    )
    new_email = models.EmailField()
    credential_hash = models.CharField(max_length=64, editable=False)
    token_hash = models.CharField(
        max_length=64, unique=True, null=True, blank=True, editable=False
    )
    issued_at = models.DateTimeField(null=True, blank=True, editable=False)
    expires_at = models.DateTimeField(
        null=True, blank=True, db_index=True, editable=False
    )
    confirmed_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(new_email=Lower(Trim("new_email")))
                & ~models.Q(new_email=""),
                name="email_change_address_canonical",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        token_hash__isnull=True,
                        issued_at__isnull=True,
                        expires_at__isnull=True,
                        confirmed_at__isnull=True,
                    )
                    | (
                        models.Q(
                            token_hash__isnull=False,
                            issued_at__isnull=False,
                            expires_at__isnull=False,
                            expires_at__gt=models.F("issued_at"),
                        )
                        & ~models.Q(token_hash="")
                        & (
                            models.Q(confirmed_at__isnull=True)
                            | models.Q(confirmed_at__gte=models.F("issued_at"))
                        )
                    )
                ),
                name="email_change_proof_state_valid",
            ),
        ]


class RequestRateLimit(models.Model):
    """A shared fixed-window counter for authentication attempts or organization work."""

    # Namespaced keyed digests identify counters without storing their original identifiers.
    key_hash = models.CharField(max_length=64, primary_key=True)
    request_count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)
