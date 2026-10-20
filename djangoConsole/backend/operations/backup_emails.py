# FileName: backup_emails.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import UTC

from django.conf import settings
from django.core.mail import EmailMessage

from notifications.models import EmailType, EmailDelivery


def build_backup_notice(delivery: EmailDelivery) -> EmailMessage:
    """Describe the recorded transition without including server paths or backup contents."""
    if delivery.email_type == EmailType.BACKUP_FAILURE_NOTICE:
        strSubject = "LiberRPA Console backup needs attention"
        strMessage = "A backup failed, or some older backups could not be removed."
    elif delivery.email_type == EmailType.BACKUP_RECOVERY_NOTICE:
        strSubject = "LiberRPA Console backups recovered"
        strMessage = "A new backup completed successfully. No backup cleanup errors remain."
    else:
        raise ValueError("A backup notice is required.")
    strRecordedAt = delivery.created_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    return EmailMessage(
        subject=strSubject,
        body=(
            f"{strMessage}\n\nRecorded at: {strRecordedAt}\n\n"
            f"View the result: {settings.CONSOLE_URL}/platform/maintenance\n\nLiberRPA Console\n"
        ),
        to=[delivery.recipient],
    )
