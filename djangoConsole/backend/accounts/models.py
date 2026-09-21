# FileName: models.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.core.validators import ProhibitNullCharactersValidator
from django.db import models
from django.db.models.functions import Lower, Trim
from django.utils import timezone
from django.utils.crypto import salted_hmac

from console_project.validators import validate_time_zone

from .passwords import validate_new_password


class UserManager(BaseUserManager["User"]):
    @classmethod
    def normalize_email(cls, email: str) -> str:
        # Reuse Django's Unicode normalization; email casing is not significant here.
        return AbstractBaseUser.normalize_username(email).strip().lower()

    def get_by_natural_key(self, username: str) -> "User":
        # Django calls the login identifier "username", even for email login.
        return self.get(email=self.normalize_email(username))

    async def aget_by_natural_key(self, username: str) -> "User":
        return await self.aget(email=self.normalize_email(username))

    def create_user(
        self,
        email: str,
        password: str | None = None,
        *,
        username: str,
        timeZone: str = "UTC",
    ) -> "User":
        """Create an account record; callers handle verified registration and membership."""
        user = self.model(
            email=self.normalize_email(email),
            username=username.strip(),
            time_zone=timeZone,
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
    email = models.EmailField(unique=True)
    username = models.CharField(
        max_length=150, validators=[ProhibitNullCharactersValidator()]
    )
    time_zone = models.CharField(
        max_length=100, default="UTC", validators=[validate_time_zone]
    )
    # Reserved for platform suspension, not an ordinary member-management switch.
    is_active = models.BooleanField(default=True)
    session_version = models.PositiveBigIntegerField(default=0, editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(email=Lower(Trim("email"))) & ~models.Q(email=""),
                name="accounts_user_email_canonical",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.username} ({self.email})"

    def _get_session_auth_hash(self, secret: str | None = None) -> str:
        """Include the revocation version in Django's normal and fallback session hashes."""
        # NOTE: Version zero preserves existing sessions when this field is first added.
        keySalt = "django.contrib.auth.models.AbstractBaseUser.get_session_auth_hash"
        authValue = self.password
        if self.session_version != 0:
            keySalt = "accounts.User.get_session_auth_hash"
            authValue = f"{self.password}:{self.session_version}"
        return salted_hmac(
            keySalt,
            authValue,
            secret=secret,
            algorithm="sha256",
        ).hexdigest()


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


class AuthenticationRequestLimit(models.Model):
    """A shared request counter for one IP address, registration token, or login email."""

    # Namespaced keyed digests identify counters without storing IP addresses, tokens, or emails.
    source_hash = models.CharField(max_length=64, primary_key=True)
    request_count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)
