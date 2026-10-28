# FileName: config.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from dataclasses import dataclass, field
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
    model_validator,
)

from .constants import INT_MAX_JSON_INTEGER, INT_MAX_RUN_LOG_RETENTION_DAYS

_LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "[::1]")

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
SingleLineText = Annotated[
    NonEmptyText, StringConstraints(pattern=r"^[^\x00-\x1f\x7f]+$")
]


def _validate_email_address(address: str) -> str:
    try:
        validate_email(address)
    except DjangoValidationError:
        raise ValueError("Enter a valid email address without a display name.") from None
    return address


EmailAddress = Annotated[NonEmptyText, AfterValidator(_validate_email_address)]


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


class FileTransferProxyConfig(_BaseConfig):
    host: NonEmptyText = "127.0.0.1"
    port: int = Field(default=9999, ge=1, le=65535)


# Limits must round-trip exactly through browser JSON numbers.
# NOTE: Fields with their own upper bound use int to avoid merging two le constraints.
LimitInteger = Annotated[int, Field(le=INT_MAX_JSON_INTEGER)]


class LimitsConfig(_BaseConfig):
    # Size limits are in bytes; size comments use binary units (KiB, MiB, GiB).
    # Shared across accounts and credential channels, independently for each organization.
    # Separate fixed 60-second windows; batch writes charge the requested object count.
    # Zero blocks the corresponding ordinary operations.
    organizationReadRequestsPerMinute: int = Field(default=1200, ge=0, le=2147483647)
    organizationWriteObjectsPerMinute: int = Field(default=600, ge=0, le=2147483647)

    # Organization capacity.
    # Members include administrators, inactive members, and unexpired pending invitations.
    maxMembersPerOrganization: LimitInteger = Field(default=50, ge=0)
    maxDepartmentsPerOrganization: LimitInteger = Field(default=20, ge=0)
    # Top-level departments have depth 1.
    maxDepartmentDepth: LimitInteger = Field(default=5, ge=1)
    # Paused and unassociated Executor records still count.
    maxExecutorsPerOrganization: LimitInteger = Field(default=20, ge=0)
    # Empty groups still count.
    maxExecutorGroupsPerOrganization: LimitInteger = Field(default=50, ge=0)
    # A project is a department/name pair represented by uploaded packages.
    maxProjectsPerOrganization: LimitInteger = Field(default=100, ge=0)
    # Package versions count separately within that project.
    maxPackagesPerProject: LimitInteger = Field(default=20, ge=0)
    maxPackageBytes: int = Field(default=536870912, ge=1, le=536870912)  # 512 MiB
    maxSchedulesPerOrganization: LimitInteger = Field(default=200, ge=0)
    maxActiveJobsPerOrganization: LimitInteger = Field(default=500, ge=0)
    # Refill rate and maximum accumulated allowance; each new Job costs one unit.
    # A zero refill rate preserves the remaining allowance but never replenishes it.
    newJobsPerMinute: LimitInteger = Field(default=60, ge=0)
    newJobsBurst: LimitInteger = Field(default=120, ge=1)
    # Age and count limits apply to finished or administratively closed Job groups.
    runHistoryRetentionDays: int = Field(default=720, ge=1, le=720)
    maxRunHistoryPerOrganization: LimitInteger = Field(default=20000, ge=1)
    runLogRetentionDays: int = Field(
        default=INT_MAX_RUN_LOG_RETENTION_DAYS, ge=1, le=INT_MAX_RUN_LOG_RETENTION_DAYS
    )
    maxRunLogBytesPerOrganization: LimitInteger = Field(default=5368709120, ge=0)  # 5 GiB
    maxRunLogGroupsPerOrganization: LimitInteger = Field(default=10000, ge=0)
    # Counts non-member addresses; current member email addresses are available automatically.
    maxRunEmailAddressesPerOrganization: LimitInteger = Field(default=100, ge=0)
    # Hour and 24-hour limits use rolling windows; the organization day limit uses UTC calendar days.
    maxRunEmailRecipientsPerOrganizationHour: LimitInteger = Field(default=100, ge=0)
    maxRunEmailRecipientsPerOrganizationDay: LimitInteger = Field(default=500, ge=0)
    maxRunEmailRecipientsPerAddressHour: LimitInteger = Field(default=30, ge=0)
    maxRunEmailRecipientsPer24Hours: LimitInteger = Field(default=2000, ge=0)
    maxNotificationsPerAccount: LimitInteger = Field(default=200, ge=0)
    notificationRetentionDays: LimitInteger = Field(default=30, ge=1)
    maxAssetsPerOrganization: LimitInteger = Field(default=1000, ge=0)
    # UTF-8 size of text or compact JSON; Credential fields count together.
    maxAssetValueBytes: int = Field(default=65536, ge=1, le=262144)  # 64 KiB
    maxSecretAssetValueBytes: int = Field(default=16384, ge=1, le=262144)  # 16 KiB

    # Queue capacity counts queued and claimed items; reducing it never deletes business data.
    maxDataQueuesPerOrganization: LimitInteger = Field(default=50, ge=0)
    maxQueueItemsPerOrganization: LimitInteger = Field(default=20000, ge=0)
    maxQueueDataBytesPerOrganization: LimitInteger = Field(
        default=104857600, ge=0
    )  # 100 MiB
    maxQueueItemBytes: int = Field(default=1048576, ge=1, le=1048576)  # 1 MiB
    # Unexpired receipts are retained; a full receipt budget blocks new mutations.
    queueReceiptRetentionDays: int = Field(default=30, ge=30, le=3650)
    maxQueueReceiptsPerOrganization: LimitInteger = Field(default=100000, ge=1)

    # Packages and shared files share storage; garbage remains charged until cleanup succeeds.
    # Replacing a file reserves the full new size before releasing the old file.
    maxStoredBytesPerOrganization: LimitInteger = Field(default=5368709120, ge=0)  # 5 GiB
    # Zero blocks new filenames but still permits replacing existing files.
    maxSharedFilesPerOrganization: LimitInteger = Field(default=5000, ge=0)
    maxSharedFileBytes: int = Field(default=20971520, ge=0, le=20971520)  # 20 MiB
    # Free-space reserve after pending writes; zero removes the extra reserve.
    minStorageFreeBytes: LimitInteger = Field(default=5368709120, ge=0)  # 5 GiB
    # Separate transfer limits; zero blocks new transfers in that direction.
    # Downloads include Run files; relaying a Run file does not also consume an upload slot.
    maxActiveUploadsPerOrganization: LimitInteger = Field(default=20, ge=0)
    maxActiveDownloadsPerOrganization: LimitInteger = Field(default=20, ge=0)
    # Unexpired receipts are retained; a full receipt budget blocks new mutations.
    fileReceiptRetentionDays: int = Field(default=30, ge=30, le=3650)
    maxFileReceiptsPerOrganization: LimitInteger = Field(default=100000, ge=1)

    # Both age and count limits apply; cleanup is independent of business object and API key retention.
    auditRetentionDays: int = Field(default=180, ge=1, le=180)
    maxAuditRecordsPerOrganization: LimitInteger = Field(default=100000, ge=1)
    maxPlatformAuditRecords: LimitInteger = Field(default=100000, ge=1)

    # API key capacity and inactive metadata retention per account.
    # Expired and revoked keys do not consume active capacity; zero blocks new keys.
    maxActiveApiKeysPerAccount: LimitInteger = Field(default=10, ge=0)
    # Either retention limit set to zero disables inactive metadata retention; Notes edits do not extend it.
    inactiveApiKeyRetentionDays: int = Field(default=30, ge=0, le=3650)
    maxInactiveApiKeysPerAccount: LimitInteger = Field(default=100, ge=0)

    # Completed email history; active accounting and unprocessed deliveries remain protected.
    emailDeliveryRetentionDays: int = Field(default=30, ge=1, le=30)
    maxEmailDeliveriesPerOrganization: LimitInteger = Field(default=10000, ge=0)
    maxEmailDeliveriesWithoutOrganization: LimitInteger = Field(default=10000, ge=0)

    # Rolling 24-hour recipient budget; failed or uncertain SMTP attempts still count.
    # Zero prevents new SMTP attempts.
    maxEmailRecipientsPer24Hours: LimitInteger = Field(default=2500, ge=0)
    # Maximum accumulated recipient allowance.
    emailBurstRecipients: LimitInteger = Field(default=100, ge=1)
    # Seconds needed to replenish one recipient unit.
    emailRefillSeconds: LimitInteger = Field(default=30, ge=1)

    # Resend cooldown: per address for registration/recovery, organization/address for invitations, and account for email changes.
    emailResendSeconds: int = Field(default=300, ge=300, le=86400)

    # Successful attempts and unknown accounts also count; both source and account allowances must remain.
    # Zero blocks login; failures do not disable the account.
    loginRequestsPerSource: int = Field(default=30, ge=0, le=2147483647)
    loginRequestsPerAccount: int = Field(default=10, ge=0, le=2147483647)
    loginRequestWindowSeconds: int = Field(default=600, ge=1, le=86400)

    # Bearer resource and execution-control authentication use separate source-IP counters with these limits.
    # Successful, malformed, and unknown credentials count; zero blocks requests.
    apiKeyRequestsPerSource: int = Field(default=2400, ge=0, le=2147483647)
    apiKeyRequestWindowSeconds: int = Field(default=60, ge=1, le=86400)

    # Editor contact, Executor contact, and Python resource traffic use independent source-IP counters.
    nativeClientRequestsPerSource: int = Field(default=2400, ge=0, le=2147483647)
    nativeClientRequestWindowSeconds: int = Field(default=60, ge=1, le=86400)
    # Offline does not release a valid Executor association.
    executorOfflineSeconds: int = Field(default=60, ge=30, le=3600)

    # Registration and recovery email requests count separately, including suppressed requests.
    publicEmailRequestsPerSource: int = Field(default=10, ge=0, le=2147483647)
    publicEmailRequestWindowSeconds: int = Field(default=600, ge=1, le=86400)

    # Invitations, account security actions, API key creation, and organization deletion count per flow.
    # Both source and acting-account allowances must remain; failed password checks also count.
    sensitiveActionRequestsPerSource: int = Field(default=30, ge=0, le=2147483647)
    sensitiveActionRequestsPerAccount: int = Field(default=10, ge=0, le=2147483647)
    sensitiveActionRequestWindowSeconds: int = Field(default=600, ge=1, le=86400)

    # Email-link checks and submissions share these settings and count per flow.
    # Both source and token allowances must remain; zero blocks requests.
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


class BackupConfig(_BaseConfig):
    location: NonEmptyText
    dailyTime: Annotated[
        str, StringConstraints(pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    ] = "03:00"
    notificationEmail: EmailAddress


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
    fileTransferProxy: FileTransferProxyConfig | None = None
    backup: BackupConfig | None = None
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    consoleUrl: HttpUrl
    supportEmail: EmailAddress
    smtp: SmtpConfig

    @model_validator(mode="after")
    def require_file_transfer_proxy(self) -> "ConsoleConfig":
        if self.fileTransferProxy is None and self.consoleUrl.host not in _LOOPBACK_HOSTS:
            raise ValueError(
                "File transfer proxy settings are required for a public Console URL."
            )
        return self

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
        if consoleUrl.scheme != "https" and consoleUrl.host not in _LOOPBACK_HOSTS:
            raise ValueError(
                "Console URL must use HTTPS, except on the local loopback host."
            )
        return consoleUrl


def parse_config(content: bytes, configPath: Path) -> ConsoleConfig:
    """Validate the exact configuration bytes used by startup or a backup bundle."""
    try:
        dictConfig = json5.loads(content.decode("utf-8-sig"), allow_duplicate_keys=False)
    except (ValueError, UnicodeError):
        raise ImproperlyConfigured(
            f"Invalid JSONC or duplicate configuration keys: {configPath}"
        ) from None

    try:
        return ConsoleConfig.model_validate(dictConfig)
    except ValidationError as e:
        raise ImproperlyConfigured(f"Invalid Console configuration: {e}") from None


@dataclass(frozen=True)
class ConsoleConfigSnapshot:
    configPath: Path
    config: ConsoleConfig
    secrets: dict[str, bytes] = field(repr=False)

    def read_secret(self, fileName: str) -> str:
        try:
            strSecretValue = self.secrets[fileName].decode("utf-8-sig").rstrip("\r\n")
        except UnicodeError:
            raise ImproperlyConfigured(f"Cannot read secret file: {fileName}") from None
        if not strSecretValue.strip():
            raise ImproperlyConfigured(f"Secret file is empty: {fileName}")
        return strSecretValue

    def read_secret_cipher(self) -> MultiFernet | None:
        """Use the same fixed key bytes for running services and their backups."""
        if not self.config.encryptionKeyFiles:
            return None
        listCipher: list[Fernet] = []
        for strKeyFile in self.config.encryptionKeyFiles:
            try:
                listCipher.append(Fernet(self.read_secret(strKeyFile)))
            except (ValueError, UnicodeError):
                raise ImproperlyConfigured(
                    f"Invalid encryption key file: {strKeyFile}"
                ) from None
        return MultiFernet(listCipher)


def read_config_snapshot(configPath: Path) -> ConsoleConfigSnapshot:
    try:
        content = configPath.read_bytes()
    except OSError as e:
        raise ImproperlyConfigured(
            f"Cannot read Console configuration: {configPath}"
        ) from e
    config = parse_config(content, configPath)
    dictSecret: dict[str, bytes] = {}
    for strFileName in dict.fromkeys([
        config.secretKeyFile,
        config.database.passwordFile,
        config.smtp.passwordFile,
        *config.encryptionKeyFiles,
    ]):
        try:
            dictSecret[strFileName] = (configPath.parent / strFileName).read_bytes()
        except OSError as e:
            raise ImproperlyConfigured(f"Cannot read secret file: {strFileName}") from e
    return ConsoleConfigSnapshot(configPath, config, dictSecret)
