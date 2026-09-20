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
from django.core.mail.backends.base import BaseEmailBackend
from django.views.decorators.debug import sensitive_variables

from .models import EmailStatus


@dataclass(frozen=True)
class SmtpResult:
    """A bounded outcome without SMTP replies, message content, or credentials."""

    status: EmailStatus
    reasonCode: str = ""


@sensitive_variables()
def _send_email_on_open_connection(
    mailer: BaseEmailBackend, emailMessage: EmailMessage
) -> SmtpResult:
    try:
        sentMessageCount = mailer.send_messages([emailMessage])
    except (SMTPResponseException, SMTPRecipientsRefused):
        return SmtpResult(status=EmailStatus.FAILED, reasonCode="smtp_rejected")
    except SMTPNotSupportedError:
        return SmtpResult(status=EmailStatus.FAILED, reasonCode="smtp_not_supported")
    except ValueError:
        # Django prepares headers and message bytes before passing them to SMTP.
        return SmtpResult(status=EmailStatus.FAILED, reasonCode="email_message_invalid")
    except OSError:
        # SMTP exceptions also inherit OSError; a lost reply can hide successful acceptance.
        return SmtpResult(status=EmailStatus.UNKNOWN, reasonCode="smtp_result_unknown")

    if sentMessageCount == 1:
        return SmtpResult(status=EmailStatus.ACCEPTED)
    if sentMessageCount == 0:
        return SmtpResult(status=EmailStatus.FAILED, reasonCode="smtp_not_accepted")
    return SmtpResult(status=EmailStatus.UNKNOWN, reasonCode="smtp_result_unknown")


@sensitive_variables()
def send_smtp_once(emailMessage: EmailMessage) -> SmtpResult:
    """Attempt one prepared recipient using the configured SMTP mailer, without retrying.

    The caller must commit the recipient reservation before calling this function.
    The message comes from a trusted builder; SMTP performs its own encoding and validation.
    Accepted means SMTP accepted the message, not that it reached the recipient's inbox.
    """
    if len(emailMessage.recipients()) != 1:
        raise ValueError("An SMTP attempt must contain exactly one budgeted recipient.")

    # Django creates a fresh connection for this access; do not share it between attempts.
    mailer = mailers["default"]
    try:
        try:
            # Open explicitly so send_messages() cannot hide its result behind a close error.
            mailer.open()
        except SMTPAuthenticationError:
            return SmtpResult(
                status=EmailStatus.FAILED, reasonCode="smtp_authentication_failed"
            )
        except SMTPNotSupportedError:
            return SmtpResult(status=EmailStatus.FAILED, reasonCode="smtp_not_supported")
        except ssl.SSLError:
            return SmtpResult(status=EmailStatus.FAILED, reasonCode="smtp_tls_failed")
        except ValueError:
            return SmtpResult(
                status=EmailStatus.FAILED, reasonCode="smtp_configuration_invalid"
            )
        except OSError:
            # No message has been submitted during connection, TLS negotiation, or login.
            return SmtpResult(
                status=EmailStatus.FAILED, reasonCode="smtp_connection_failed"
            )

        return _send_email_on_open_connection(mailer, emailMessage)
    finally:
        try:
            mailer.close()
        except OSError:
            # A QUIT failure cannot change an already known delivery result.
            pass
