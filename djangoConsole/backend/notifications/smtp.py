# FileName: smtp.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import ssl
from dataclasses import dataclass
from smtplib import (
    SMTPAuthenticationError,
    SMTPNotSupportedError,
    SMTPRecipientsRefused,
    SMTPResponseException,
)

from django.core.mail import EmailMessage, mailers
from django.views.decorators.debug import sensitive_variables

from .models import EmailStatus, EmailReasonCode


@dataclass(frozen=True)
class SmtpResult:
    """A bounded outcome without SMTP replies, message content, or credentials."""

    status: EmailStatus
    reasonCode: EmailReasonCode = EmailReasonCode.NONE


@sensitive_variables()
def send_smtp_once(emailMessage: EmailMessage) -> SmtpResult:
    """Attempt one prepared recipient using the configured SMTP mailer, without retrying.

    The caller must commit the recipient reservation before calling this function.
    The message comes from a trusted builder; SMTP performs its own encoding and validation.
    Accepted means SMTP accepted the message, not that it reached the recipient's inbox.
    """
    if len(emailMessage.recipients()) != 1:
        raise ValueError("An SMTP attempt must contain exactly one budgeted recipient.")

    # Create one backend per attempt from the configured MAILERS alias.
    mailer = mailers["default"]
    try:
        try:
            # Open explicitly so send_messages() cannot hide its result behind a close error.
            mailer.open()
        except SMTPAuthenticationError:
            return SmtpResult(
                status=EmailStatus.FAILED,
                reasonCode=EmailReasonCode.SMTP_AUTHENTICATION_FAILED,
            )
        except SMTPNotSupportedError:
            return SmtpResult(
                status=EmailStatus.FAILED, reasonCode=EmailReasonCode.SMTP_NOT_SUPPORTED
            )
        except ssl.SSLError:
            return SmtpResult(
                status=EmailStatus.FAILED, reasonCode=EmailReasonCode.SMTP_TLS_FAILED
            )
        except ValueError:
            return SmtpResult(
                status=EmailStatus.FAILED,
                reasonCode=EmailReasonCode.SMTP_CONFIGURATION_INVALID,
            )
        except OSError:
            # No message has been submitted during connection, TLS negotiation, or login.
            return SmtpResult(
                status=EmailStatus.FAILED,
                reasonCode=EmailReasonCode.SMTP_CONNECTION_FAILED,
            )

        try:
            intSentMessageCount = mailer.send_messages([emailMessage])
        except (SMTPResponseException, SMTPRecipientsRefused):
            return SmtpResult(
                status=EmailStatus.FAILED, reasonCode=EmailReasonCode.SMTP_REJECTED
            )
        except SMTPNotSupportedError:
            return SmtpResult(
                status=EmailStatus.FAILED, reasonCode=EmailReasonCode.SMTP_NOT_SUPPORTED
            )
        except ValueError:
            # Django prepares headers and message bytes before passing them to SMTP.
            return SmtpResult(
                status=EmailStatus.FAILED,
                reasonCode=EmailReasonCode.EMAIL_MESSAGE_INVALID,
            )
        except OSError:
            # SMTP exceptions also inherit OSError; a lost reply can hide successful acceptance.
            return SmtpResult(
                status=EmailStatus.UNKNOWN, reasonCode=EmailReasonCode.SMTP_RESULT_UNKNOWN
            )

        if intSentMessageCount == 1:
            return SmtpResult(status=EmailStatus.ACCEPTED)
        if intSentMessageCount == 0:
            return SmtpResult(
                status=EmailStatus.FAILED, reasonCode=EmailReasonCode.SMTP_NOT_ACCEPTED
            )
        return SmtpResult(
            status=EmailStatus.UNKNOWN, reasonCode=EmailReasonCode.SMTP_RESULT_UNKNOWN
        )
    finally:
        try:
            mailer.close()
        except OSError:
            # A QUIT failure cannot change an already known delivery result.
            pass
