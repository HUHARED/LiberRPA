# FileName: config.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from pathlib import Path
from typing import Annotated, Literal, Self

import json5
from django.core.exceptions import ImproperlyConfigured
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)

type NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
type SingleLineText = Annotated[
    NonEmptyText, StringConstraints(pattern=r"^[^\x00-\x1f\x7f]+$")
]


def _validate_email_address(address: str) -> str:
    try:
        validate_email(address)
    except DjangoValidationError:
        raise ValueError("Enter a valid email address without a display name.") from None
    return address


type EmailAddress = Annotated[NonEmptyText, AfterValidator(_validate_email_address)]


class _BaseConfig(BaseModel):
    model_config = ConfigDict(
        strict=True, extra="forbid", frozen=True, hide_input_in_errors=True
    )


class DatabaseConfig(_BaseConfig):
    host: NonEmptyText
    port: int = Field(ge=1, le=65535)
    name: NonEmptyText
    user: NonEmptyText
    passwordFile: NonEmptyText


class LimitsConfig(_BaseConfig):
    maxMembersPerOrganization: int = Field(default=50, ge=0)
    invitationResendSeconds: int = Field(default=300, ge=300, le=86400)
    invitationEmailRequestsPerSource: int = Field(default=30, ge=0, le=2147483647)
    invitationEmailRequestsPerAccount: int = Field(default=10, ge=0, le=2147483647)
    invitationEmailRequestWindowSeconds: int = Field(default=600, ge=1, le=86400)
    maxDepartmentsPerOrganization: int = Field(default=20, ge=0)
    maxDepartmentDepth: int = Field(default=5, ge=1)
    maxEmailRecipientsPer24Hours: int = Field(default=2500, ge=0)
    emailBurstRecipients: int = Field(default=100, ge=1)
    emailRefillSeconds: int = Field(default=30, ge=1)
    registrationEmailRequestsPerSource: int = Field(default=10, ge=0, le=2147483647)
    registrationEmailRequestWindowSeconds: int = Field(default=600, ge=1, le=86400)
    registrationTokenRequestsPerSource: int = Field(default=30, ge=0, le=2147483647)
    registrationTokenRequestsPerToken: int = Field(default=10, ge=0, le=2147483647)
    registrationTokenRequestWindowSeconds: int = Field(default=600, ge=1, le=86400)
    loginRequestsPerSource: int = Field(default=30, ge=0, le=2147483647)
    loginRequestsPerAccount: int = Field(default=10, ge=0, le=2147483647)
    loginRequestWindowSeconds: int = Field(default=600, ge=1, le=86400)
    passwordChangeRequestsPerSource: int = Field(default=30, ge=0, le=2147483647)
    passwordChangeRequestsPerAccount: int = Field(default=10, ge=0, le=2147483647)
    passwordChangeRequestWindowSeconds: int = Field(default=600, ge=1, le=86400)
    sessionRevocationRequestsPerSource: int = Field(default=30, ge=0, le=2147483647)
    sessionRevocationRequestsPerAccount: int = Field(default=10, ge=0, le=2147483647)
    sessionRevocationRequestWindowSeconds: int = Field(default=600, ge=1, le=86400)
    passwordResetResendSeconds: int = Field(default=300, ge=300, le=86400)
    passwordResetEmailRequestsPerSource: int = Field(default=10, ge=0, le=2147483647)
    passwordResetEmailRequestWindowSeconds: int = Field(default=600, ge=1, le=86400)
    passwordResetTokenRequestsPerSource: int = Field(default=30, ge=0, le=2147483647)
    passwordResetTokenRequestsPerToken: int = Field(default=10, ge=0, le=2147483647)
    passwordResetTokenRequestWindowSeconds: int = Field(default=600, ge=1, le=86400)
    emailChangeResendSeconds: int = Field(default=300, ge=300, le=86400)
    emailChangeEmailRequestsPerSource: int = Field(default=30, ge=0, le=2147483647)
    emailChangeEmailRequestsPerAccount: int = Field(default=10, ge=0, le=2147483647)
    emailChangeEmailRequestWindowSeconds: int = Field(default=600, ge=1, le=86400)
    emailChangeTokenRequestsPerSource: int = Field(default=30, ge=0, le=2147483647)
    emailChangeTokenRequestsPerToken: int = Field(default=10, ge=0, le=2147483647)
    emailChangeTokenRequestWindowSeconds: int = Field(default=600, ge=1, le=86400)


class SmtpConfig(_BaseConfig):
    host: SingleLineText
    port: int = Field(ge=1, le=65535)
    security: Literal["ssl", "starttls"]
    user: SingleLineText
    passwordFile: NonEmptyText
    fromEmail: EmailAddress
    fromName: SingleLineText = "LiberRPA Console"
    timeoutSeconds: int = Field(default=10, ge=1)


class ConsoleConfig(_BaseConfig):
    debug: bool = False
    allowedHosts: list[NonEmptyText] = Field(min_length=1)
    secretKeyFile: NonEmptyText
    database: DatabaseConfig
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    # These may be absent during backend development; configure all three before sending mail.
    consoleUrl: HttpUrl | None = None
    supportEmail: EmailAddress | None = None
    smtp: SmtpConfig | None = None

    @field_validator("consoleUrl")
    @classmethod
    def validate_console_url(cls, consoleUrl: HttpUrl | None) -> HttpUrl | None:
        if consoleUrl is None:
            return None
        if (
            consoleUrl.username is not None
            or consoleUrl.password is not None
            or consoleUrl.query is not None
            or consoleUrl.fragment is not None
            or consoleUrl.path not in (None, "/")
        ):
            raise ValueError(
                "Console URL must be a site root without credentials, a query, or a fragment."
            )
        if consoleUrl.scheme != "https" and consoleUrl.host not in (
            "localhost",
            "127.0.0.1",
            "[::1]",
        ):
            raise ValueError(
                "Console URL must use HTTPS, except on the local loopback host."
            )
        return consoleUrl

    @model_validator(mode="after")
    def validate_email_configuration(self) -> Self:
        emailConfigurationFlags = (
            self.consoleUrl is not None,
            self.supportEmail is not None,
            self.smtp is not None,
        )
        if any(emailConfigurationFlags) and not all(emailConfigurationFlags):
            raise ValueError("Configure consoleUrl, supportEmail, and smtp together.")
        return self


def read_config(configPath: Path) -> ConsoleConfig:
    try:
        strConfig = configPath.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as e:
        raise ImproperlyConfigured(
            f"Cannot read Console configuration: {configPath}"
        ) from e

    try:
        dictConfig = json5.loads(strConfig, allow_duplicate_keys=False)
    except ValueError:
        raise ImproperlyConfigured(
            f"Invalid JSONC or duplicate configuration keys: {configPath}"
        ) from None

    try:
        return ConsoleConfig.model_validate(dictConfig)
    except ValidationError as e:
        raise ImproperlyConfigured(f"Invalid Console configuration: {e}") from None


def read_secret_file(secretPath: Path) -> str:
    try:
        # Remove text-file line endings without changing spaces in a password.
        secretValue = secretPath.read_text(encoding="utf-8-sig").rstrip("\r\n")
    except (OSError, UnicodeError) as e:
        raise ImproperlyConfigured(f"Cannot read secret file: {secretPath}") from e

    if not secretValue.strip():
        raise ImproperlyConfigured(f"Secret file is empty: {secretPath}")
    return secretValue
