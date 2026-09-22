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
    MEMBER_INVITATION = "member_invitation", "Member invitation"
    ORGANIZATION_REGISTRATION = "organization_registration", "Organization registration"
    PASSWORD_RESET = "password_reset", "Password reset"
    EMAIL_CHANGE_VERIFICATION = "email_change_verification", "Email change verification"
    EMAIL_CHANGE_NOTICE = "email_change_notice", "Email change notice"


class EmailStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SENDING = "sending", "Sending"
    ACCEPTED = "accepted", "Accepted by SMTP"
    FAILED = "failed", "Failed"
    NOT_SENT = "not_sent", "Not sent"
    UNKNOWN = "unknown", "Unknown"


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
    email_type = models.CharField(max_length=32, choices=EmailType.choices)
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
        max_length=16, choices=EmailStatus.choices, default=EmailStatus.PENDING
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    attempted_at = models.DateTimeField(null=True, blank=True, editable=False)
    finished_at = models.DateTimeField(null=True, blank=True, editable=False)
    # Store a controlled reason code, never an SMTP reply, message body, or traceback.
    reason_code = models.CharField(max_length=64, blank=True, default="")

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
                    models.Q(
                        email_type=EmailType.MEMBER_INVITATION,
                        invitation__isnull=False,
                        invitation_request_id__isnull=False,
                    )
                    | models.Q(
                        email_type__in=[
                            EmailType.ORGANIZATION_REGISTRATION,
                            EmailType.PASSWORD_RESET,
                            EmailType.EMAIL_CHANGE_VERIFICATION,
                            EmailType.EMAIL_CHANGE_NOTICE,
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
                        reason_code="",
                    )
                    | models.Q(
                        status=EmailStatus.SENDING,
                        attempted_at__isnull=False,
                        finished_at__isnull=True,
                        reason_code="",
                    )
                    | models.Q(
                        status=EmailStatus.ACCEPTED,
                        attempted_at__isnull=False,
                        finished_at__isnull=False,
                        reason_code="",
                    )
                    | (
                        models.Q(
                            status__in=[EmailStatus.FAILED, EmailStatus.UNKNOWN],
                            attempted_at__isnull=False,
                            finished_at__isnull=False,
                        )
                        & ~models.Q(reason_code="")
                    )
                    | (
                        models.Q(
                            status=EmailStatus.NOT_SENT,
                            attempted_at__isnull=True,
                            finished_at__isnull=False,
                        )
                        & ~models.Q(reason_code="")
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
