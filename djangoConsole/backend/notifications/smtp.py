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
from typing import cast

from django.conf import settings
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMessage
from django.core.mail.backends.base import BaseEmailBackend
from django.utils.module_loading import import_string
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

    # Build a fresh connection for each attempt; do not share it between attempts.
    dictMailer = settings.MAILERS.get("default")
    if dictMailer is None:
        raise ImproperlyConfigured("Configure the default Console email backend.")
    mailerFactory = getattr(mail, "mailers", None)
    if mailerFactory is not None:
        # NOTE: Django 6.1 needs the factory's alias to use MAILERS instead of legacy settings.
        mailer = cast(BaseEmailBackend, mailerFactory["default"])
    else:
        # Older Django versions need an explicit backend and must not default to localhost SMTP.
        mailerClass = cast(type[BaseEmailBackend], import_string(dictMailer["BACKEND"]))
        mailer = mailerClass(**dictMailer.get("OPTIONS", {}))
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
