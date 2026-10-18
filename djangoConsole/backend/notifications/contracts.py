# FileName: contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self
from uuid import UUID

from django.db.models import TextChoices
from pydantic import Field, model_validator

from console_project.contracts import JsonRequest, JsonResponsePayload
from console_project.validators import validate_json_string


class EmailStatus(TextChoices):
    PENDING = "pending", "Pending"
    SENDING = "sending", "Sending"
    ACCEPTED = "accepted", "Accepted by SMTP"
    FAILED = "failed", "Failed"
    NOT_SENT = "not_sent", "Not sent"
    UNKNOWN = "unknown", "Unknown"


class EmailReasonCode(TextChoices):
    RUN_NOT_ELIGIBLE = "run_not_eligible", "Run email is no longer eligible"
    RUN_BUDGET_EXHAUSTED = "run_budget_exhausted", "Run email budget exhausted"
    RECIPIENT_NOT_ELIGIBLE = (
        "recipient_not_eligible",
        "Recipient confirmation is no longer eligible",
    )
    NONE = "", "No reason"
    SMTP_BUDGET_EXHAUSTED = "smtp_budget_exhausted", "SMTP budget exhausted"
    ORGANIZATION_CREATION_DISABLED = (
        "organization_creation_disabled",
        "Organization creation disabled",
    )
    REGISTRATION_NOT_ELIGIBLE = "registration_not_eligible", "Registration not eligible"
    ORGANIZATION_UNAVAILABLE = "organization_unavailable", "Organization unavailable"
    MEMBER_LIMIT_REACHED = "member_limit_reached", "Member limit reached"
    EMAIL_ALREADY_REGISTERED = "email_already_registered", "Email already registered"
    INVITATION_NOT_ELIGIBLE = "invitation_not_eligible", "Invitation not eligible"
    INVITATION_SUPERSEDED = "invitation_superseded", "Invitation superseded"
    PASSWORD_RESET_NOT_ELIGIBLE = (
        "password_reset_not_eligible",
        "Password reset not eligible",
    )
    EMAIL_CHANGE_NOT_ELIGIBLE = "email_change_not_eligible", "Email change not eligible"
    DELETION_NOTICE_MISSING = "deletion_notice_missing", "Deletion notice missing"
    SMTP_AUTHENTICATION_FAILED = (
        "smtp_authentication_failed",
        "SMTP authentication failed",
    )
    SMTP_NOT_SUPPORTED = "smtp_not_supported", "SMTP not supported"
    SMTP_TLS_FAILED = "smtp_tls_failed", "SMTP TLS failed"
    SMTP_CONFIGURATION_INVALID = (
        "smtp_configuration_invalid",
        "SMTP configuration invalid",
    )
    SMTP_CONNECTION_FAILED = "smtp_connection_failed", "SMTP connection failed"
    SMTP_REJECTED = "smtp_rejected", "SMTP rejected"
    EMAIL_MESSAGE_INVALID = "email_message_invalid", "Email message invalid"
    SMTP_RESULT_UNKNOWN = "smtp_result_unknown", "SMTP result unknown"
    SMTP_NOT_ACCEPTED = "smtp_not_accepted", "SMTP not accepted"
    EMAIL_WORKER_INTERRUPTED = "email_worker_interrupted", "Email worker interrupted"
    ORGANIZATION_DELETED = "organization_deleted", "Organization deleted"


INT_RUN_EMAIL_MAX_BYTES = 64 * 1024


class RunEmailOutputStatus(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"
    LIMIT = "limit"
    UNAVAILABLE = "unavailable"


class RunEmailOutputValue(JsonRequest):
    key: str
    status: Annotated[RunEmailOutputStatus, Field(strict=False)]
    text: str

    @model_validator(mode="after")
    def validate_value(self) -> Self:
        validate_json_string(self.key)
        validate_json_string(self.text)
        if self.status == RunEmailOutputStatus.AVAILABLE:
            if not self.text:
                raise ValueError("Available email values require text.")
        elif self.text:
            raise ValueError("Unavailable email values cannot contain text.")
        return self


class RecipientCreationRequest(JsonRequest):
    email: str = Field(min_length=1, max_length=254)
    notes: str = Field(default="", max_length=2000)


class RecipientNotesRequest(JsonRequest):
    notes: str = Field(max_length=2000)


class EmptyRequest(JsonRequest):
    pass


class RecipientTokenRequest(JsonRequest):
    token: str = Field(min_length=1, max_length=1000)


class RunEmailRecipientStatus(StrEnum):
    MEMBER = "member"
    VERIFIED = "verified"
    PENDING = "pending"


class RunEmailRecipientResponse(JsonResponsePayload):
    id: UUID
    email: str
    notes: str
    status: RunEmailRecipientStatus
    verified_at: datetime | None
    created_at: datetime


class RunEmailRecipientListResponse(JsonResponsePayload):
    recipients: list[RunEmailRecipientResponse]
    can_manage: bool


class RunEmailVerificationResponse(JsonResponsePayload):
    organization_name: str
    email: str
    verified: bool
