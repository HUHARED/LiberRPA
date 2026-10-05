# FileName: models.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.db import models
from django.db.models.functions import Lower, Trim
from django.utils import timezone


class EmailType(models.TextChoices):
    RUN = "run", "Run"
    RUN_RECIPIENT_VERIFICATION = (
        "run_recipient_verification",
        "Run recipient verification",
    )
    MEMBER_INVITATION = "member_invitation", "Member invitation"
    ORGANIZATION_REGISTRATION = "organization_registration", "Organization registration"
    PASSWORD_RESET = "password_reset", "Password reset"
    EMAIL_CHANGE_VERIFICATION = "email_change_verification", "Email change verification"
    EMAIL_CHANGE_NOTICE = "email_change_notice", "Email change notice"
    ORGANIZATION_DELETION_NOTICE = (
        "organization_deletion_notice",
        "Organization deletion notice",
    )


class EmailStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SENDING = "sending", "Sending"
    ACCEPTED = "accepted", "Accepted by SMTP"
    FAILED = "failed", "Failed"
    NOT_SENT = "not_sent", "Not sent"
    UNKNOWN = "unknown", "Unknown"


class EmailReasonCode(models.TextChoices):
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


class EmailDispatchState(models.Model):
    """Shared SMTP rate allowance; the row lock also serializes budget reservations."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    available_units = models.PositiveIntegerField(default=0)
    refilled_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(id=1), name="email_dispatch_state_singleton"
            )
        ]


class EmailDelivery(models.Model):
    """One delivery request and its outcome, without message bodies or usable tokens."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email_type = models.CharField(
        max_length=max(len(value) for value in EmailType.values),
        choices=EmailType.choices,
    )
    recipient = models.EmailField()
    invitation_id: uuid.UUID | None
    invitation = models.ForeignKey(
        "organizations.MemberInvitation",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="email_deliveries",
    )
    invitation_request_id = models.UUIDField(null=True, blank=True, editable=False)
    status = models.CharField(
        max_length=max(len(value) for value in EmailStatus.values),
        choices=EmailStatus.choices,
        default=EmailStatus.PENDING,
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    attempted_at = models.DateTimeField(null=True, blank=True, editable=False)
    finished_at = models.DateTimeField(null=True, blank=True, editable=False)
    # Store a controlled reason code, never an SMTP reply, message body, or traceback.
    reason_code = models.CharField(
        max_length=max(len(value) for value in EmailReasonCode.values),
        choices=EmailReasonCode.choices,
        blank=True,
        default=EmailReasonCode.NONE,
    )

    class Meta:
        indexes = [
            models.Index(
                fields=["status", "created_at"], name="email_delivery_pending_idx"
            ),
            models.Index(fields=["attempted_at"], name="email_delivery_attempt_idx"),
            models.Index(
                fields=["email_type", "recipient", "-created_at"],
                name="email_delivery_recipient_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["invitation", "invitation_request_id"],
                condition=models.Q(email_type=EmailType.MEMBER_INVITATION),
                name="one_email_per_invitation_request",
            ),
            models.CheckConstraint(
                condition=(
                    (
                        models.Q(
                            email_type=EmailType.MEMBER_INVITATION,
                            invitation_request_id__isnull=False,
                        )
                        & (
                            # Cleanup detaches historical deliveries only after suppressing pending mail.
                            models.Q(invitation__isnull=False)
                            | ~models.Q(status=EmailStatus.PENDING)
                        )
                    )
                    | models.Q(
                        email_type__in=[
                            EmailType.RUN,
                            EmailType.RUN_RECIPIENT_VERIFICATION,
                            EmailType.ORGANIZATION_REGISTRATION,
                            EmailType.PASSWORD_RESET,
                            EmailType.EMAIL_CHANGE_VERIFICATION,
                            EmailType.EMAIL_CHANGE_NOTICE,
                            EmailType.ORGANIZATION_DELETION_NOTICE,
                        ],
                        invitation__isnull=True,
                        invitation_request_id__isnull=True,
                    )
                ),
                name="email_delivery_reference_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(email_type__in=EmailType.values),
                name="email_delivery_type_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(reason_code__in=EmailReasonCode.values),
                name="email_delivery_reason_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(recipient=Lower(Trim("recipient")))
                & ~models.Q(recipient=""),
                name="email_delivery_recipient_canonical",
            ),
            models.UniqueConstraint(
                fields=["email_type", "recipient"],
                condition=models.Q(
                    email_type=EmailType.ORGANIZATION_REGISTRATION,
                    status__in=[EmailStatus.PENDING, EmailStatus.SENDING],
                ),
                name="one_active_registration_email",
            ),
            models.UniqueConstraint(
                fields=["email_type", "recipient"],
                condition=models.Q(
                    email_type=EmailType.PASSWORD_RESET,
                    status__in=[EmailStatus.PENDING, EmailStatus.SENDING],
                ),
                name="one_active_password_reset_email",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status=EmailStatus.PENDING,
                        attempted_at__isnull=True,
                        finished_at__isnull=True,
                        reason_code=EmailReasonCode.NONE,
                    )
                    | models.Q(
                        status=EmailStatus.SENDING,
                        attempted_at__isnull=False,
                        finished_at__isnull=True,
                        reason_code=EmailReasonCode.NONE,
                    )
                    | models.Q(
                        status=EmailStatus.ACCEPTED,
                        attempted_at__isnull=False,
                        finished_at__isnull=False,
                        reason_code=EmailReasonCode.NONE,
                    )
                    | (
                        models.Q(
                            status__in=[EmailStatus.FAILED, EmailStatus.UNKNOWN],
                            attempted_at__isnull=False,
                            finished_at__isnull=False,
                        )
                        & ~models.Q(reason_code=EmailReasonCode.NONE)
                    )
                    | (
                        models.Q(
                            status=EmailStatus.NOT_SENT,
                            attempted_at__isnull=True,
                            finished_at__isnull=False,
                        )
                        & ~models.Q(reason_code=EmailReasonCode.NONE)
                    )
                ),
                name="email_delivery_state_consistent",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(attempted_at__isnull=True)
                    | models.Q(attempted_at__gte=models.F("created_at"))
                )
                & (
                    models.Q(finished_at__isnull=True)
                    | models.Q(finished_at__gte=models.F("created_at"))
                )
                & (
                    models.Q(attempted_at__isnull=True)
                    | models.Q(finished_at__isnull=True)
                    | models.Q(finished_at__gte=models.F("attempted_at"))
                ),
                name="email_delivery_time_order_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.email_type}: {self.recipient} ({self.status})"


class OrganizationDeletionNotice(models.Model):
    """Minimal historical context for one completion email, independent of deleted records."""

    delivery_id: uuid.UUID
    delivery = models.OneToOneField(
        EmailDelivery, on_delete=models.CASCADE, primary_key=True, related_name="+"
    )
    organization_id = models.UUIDField(editable=False)
    organization_name = models.CharField(max_length=200, editable=False)


class RunEmailRecipient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization_id: uuid.UUID
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE
    )
    email = models.EmailField()
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_id = models.UUIDField(default=uuid.uuid4)
    verification_requested_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "email"], name="run_recipient_email_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(email=Lower(Trim("email"))) & ~models.Q(email=""),
                name="run_recipient_email_canonical",
            ),
        ]


class RunRecipientVerification(models.Model):
    delivery_id: uuid.UUID
    recipient_id: uuid.UUID

    delivery = models.OneToOneField(
        EmailDelivery, on_delete=models.CASCADE, primary_key=True
    )
    recipient = models.ForeignKey(RunEmailRecipient, on_delete=models.CASCADE)
    verification_id = models.UUIDField()


class RunEmailEvent(models.TextChoices):
    START = "start", "Started"
    COMPLETED = "completed", "Completed"
    ERROR = "error", "Error"


class RunEmailReference(models.Model):
    delivery_id: uuid.UUID
    organization_id: uuid.UUID
    recipient_id: uuid.UUID | None

    delivery = models.OneToOneField(
        EmailDelivery,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="run_reference",
    )
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE
    )
    recipient = models.ForeignKey(RunEmailRecipient, on_delete=models.SET_NULL, null=True)
    run_id = models.UUIDField()
    event = models.CharField(
        max_length=max(len(value) for value in RunEmailEvent.values),
        choices=RunEmailEvent.choices,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["run_id", "event", "recipient"],
                name="run_email_event_recipient_once",
            ),
            models.CheckConstraint(
                condition=models.Q(event__in=RunEmailEvent.values),
                name="run_email_event_valid",
            ),
        ]


class Notification(models.Model):
    organization_id: uuid.UUID
    user_id: uuid.UUID

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE
    )
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE)
    event_key = models.CharField(max_length=200)
    title = models.CharField(max_length=200)
    detail = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["user", "-created_at"], name="notification_user_time_idx"
            )
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "event_key"], name="notification_event_user_once"
            )
        ]
