# FileName: config.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from pathlib import Path
from typing import Annotated, Literal

import json5
from cryptography.fernet import Fernet, MultiFernet
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
    # Organization capacity.
    maxMembersPerOrganization: int = Field(default=50, ge=0)
    maxDepartmentsPerOrganization: int = Field(default=20, ge=0)
    maxDepartmentDepth: int = Field(default=5, ge=1)
    maxExecutorsPerOrganization: int = Field(default=20, ge=0)
    maxExecutorGroupsPerOrganization: int = Field(default=50, ge=0)
    maxProjectsPerOrganization: int = Field(default=100, ge=0)
    maxPackagesPerProject: int = Field(default=20, ge=0)
    maxPackageBytes: int = Field(default=536870912, ge=1, le=536870912)
    maxSchedulesPerOrganization: int = Field(default=200, ge=0)
    maxActiveJobsPerOrganization: int = Field(default=500, ge=0)
    newJobsPerMinute: int = Field(default=60, ge=0)
    newJobsBurst: int = Field(default=120, ge=1)
    runHistoryRetentionDays: int = Field(default=720, ge=1, le=720)
    maxRunHistoryPerOrganization: int = Field(default=20000, ge=1)
    runLogRetentionDays: int = Field(default=720, ge=1, le=720)
    maxRunLogBytesPerOrganization: int = Field(default=5368709120, ge=0)
    maxRunLogGroupsPerOrganization: int = Field(default=10000, ge=0)
    maxRunEmailAddressesPerOrganization: int = Field(default=100, ge=0)
    maxRunEmailRecipientsPerOrganizationHour: int = Field(default=100, ge=0)
    maxRunEmailRecipientsPerOrganizationDay: int = Field(default=500, ge=0)
    maxRunEmailRecipientsPerAddressHour: int = Field(default=30, ge=0)
    maxRunEmailRecipientsPer24Hours: int = Field(default=2000, ge=0)
    maxNotificationsPerAccount: int = Field(default=200, ge=0)
    notificationRetentionDays: int = Field(default=30, ge=1)
    maxAssetsPerOrganization: int = Field(default=1000, ge=0)
    maxAssetValueBytes: int = Field(default=65536, ge=1, le=262144)
    maxSecretAssetValueBytes: int = Field(default=16384, ge=1, le=262144)

    maxDataQueuesPerOrganization: int = Field(default=50, ge=0)
    maxQueueItemsPerOrganization: int = Field(default=20000, ge=0)
    maxQueueDataBytesPerOrganization: int = Field(default=104857600, ge=0)
    maxQueueItemBytes: int = Field(default=1048576, ge=1, le=1048576)
    queueReceiptRetentionDays: int = Field(default=30, ge=30, le=3650)
    maxQueueReceiptsPerOrganization: int = Field(default=100000, ge=1)

    # Packages and shared files share storage; upload and download slots are independent.
    maxStoredBytesPerOrganization: int = Field(default=5368709120, ge=0)
    maxSharedFilesPerOrganization: int = Field(default=5000, ge=0)
    maxSharedFileBytes: int = Field(default=20971520, ge=0, le=20971520)
    minStorageFreeBytes: int = Field(default=5368709120, ge=0)
    maxActiveUploadsPerOrganization: int = Field(default=4, ge=0)
    maxActiveDownloadsPerOrganization: int = Field(default=4, ge=0)
    fileReceiptRetentionDays: int = Field(default=30, ge=30, le=3650)
    maxFileReceiptsPerOrganization: int = Field(default=100000, ge=1)

    # Audit cleanup is independent of business object and API key retention.
    auditRetentionDays: int = Field(default=180, ge=1, le=180)
    maxAuditRecordsPerOrganization: int = Field(default=100000, ge=1)
    maxPlatformAuditRecords: int = Field(default=100000, ge=1)

    # API key capacity and inactive metadata retention per account.
    maxActiveApiKeysPerAccount: int = Field(default=10, ge=0)
    inactiveApiKeyRetentionDays: int = Field(default=30, ge=0, le=3650)
    maxInactiveApiKeysPerAccount: int = Field(default=100, ge=0)

    # SMTP delivery budget and rate.
    maxEmailRecipientsPer24Hours: int = Field(default=2500, ge=0)
    emailBurstRecipients: int = Field(default=100, ge=1)
    emailRefillSeconds: int = Field(default=30, ge=1)

    # Resend cooldown shared by account email flows.
    emailResendSeconds: int = Field(default=300, ge=300, le=86400)

    # Login attempts.
    loginRequestsPerSource: int = Field(default=30, ge=0, le=2147483647)
    loginRequestsPerAccount: int = Field(default=10, ge=0, le=2147483647)
    loginRequestWindowSeconds: int = Field(default=600, ge=1, le=86400)

    # Bearer authentication, independent of interactive login and credential creation.
    apiKeyRequestsPerSource: int = Field(default=2400, ge=0, le=2147483647)
    apiKeyRequestWindowSeconds: int = Field(default=60, ge=1, le=86400)

    # Editor and Executor contact use independent counters with these shared native-client limits.
    nativeClientRequestsPerSource: int = Field(default=2400, ge=0, le=2147483647)
    nativeClientRequestWindowSeconds: int = Field(default=60, ge=1, le=86400)
    executorOfflineSeconds: int = Field(default=60, ge=30, le=3600)

    # Public registration and recovery email requests count separately.
    publicEmailRequestsPerSource: int = Field(default=10, ge=0, le=2147483647)
    publicEmailRequestWindowSeconds: int = Field(default=600, ge=1, le=86400)

    # Invitations, account security actions, API key creation, and organization deletion count per flow.
    sensitiveActionRequestsPerSource: int = Field(default=30, ge=0, le=2147483647)
    sensitiveActionRequestsPerAccount: int = Field(default=10, ge=0, le=2147483647)
    sensitiveActionRequestWindowSeconds: int = Field(default=600, ge=1, le=86400)

    # Email-link checks and submissions share these settings and count per flow.
    emailTokenRequestsPerSource: int = Field(default=30, ge=0, le=2147483647)
    emailTokenRequestsPerToken: int = Field(default=10, ge=0, le=2147483647)
    emailTokenRequestWindowSeconds: int = Field(default=600, ge=1, le=86400)


class SmtpConfig(_BaseConfig):
    host: SingleLineText
    port: int = Field(ge=1, le=65535)
    security: Literal["ssl", "starttls"]
    user: SingleLineText
    passwordFile: NonEmptyText
    fromEmail: EmailAddress
    fromName: SingleLineText = "LiberRPA Console"
    timeoutSeconds: int = Field(default=10, ge=1)


class LoggingConfig(_BaseConfig):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "DEBUG"
    requests: bool = True


class ConsoleConfig(_BaseConfig):
    debug: bool = False
    allowedHosts: list[NonEmptyText] = Field(min_length=1)
    secretKeyFile: NonEmptyText
    encryptionKeyFiles: list[NonEmptyText] = Field(default_factory=list)
    storageRoot: NonEmptyText = "storage"
    database: DatabaseConfig
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    consoleUrl: HttpUrl
    supportEmail: EmailAddress
    smtp: SmtpConfig

    @field_validator("consoleUrl")
    @classmethod
    def validate_console_url(cls, consoleUrl: HttpUrl) -> HttpUrl:
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
        strSecretValue = secretPath.read_text(encoding="utf-8-sig").rstrip("\r\n")
    except (OSError, UnicodeError) as e:
        raise ImproperlyConfigured(f"Cannot read secret file: {secretPath}") from e

    if not strSecretValue.strip():
        raise ImproperlyConfigured(f"Secret file is empty: {secretPath}")
    return strSecretValue


def read_secret_cipher(configDirectory: Path, keyFiles: list[str]) -> MultiFernet | None:
    """Load the primary encryption key followed by retained decryption keys."""
    if not keyFiles:
        return None
    listCipher: list[Fernet] = []
    for strKeyFile in keyFiles:
        try:
            listCipher.append(Fernet(read_secret_file(configDirectory / strKeyFile)))
        except (ValueError, UnicodeError):
            raise ImproperlyConfigured(
                f"Invalid encryption key file: {strKeyFile}"
            ) from None
    return MultiFernet(listCipher)
