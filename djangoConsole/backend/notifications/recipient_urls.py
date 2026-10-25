# FileName: recipient_urls.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.urls import path

from . import recipient_views

urlpatterns = [
    path("", recipient_views.list_or_create_recipients, name="run-email-recipients"),
    path("templates/", recipient_views.template_metadata, name="run-email-templates"),
    path(
        "verify/",
        recipient_views.verify_recipient,
        name="run-email-recipient-verify",
    ),
    path(
        "<uuid:recipientId>/",
        recipient_views.change_recipient,
        {"action": "notes"},
        name="run-email-recipient",
    ),
    path(
        "<uuid:recipientId>/delete/",
        recipient_views.change_recipient,
        {"action": "delete"},
        name="run-email-recipient-delete",
    ),
    path(
        "<uuid:recipientId>/resend/",
        recipient_views.change_recipient,
        {"action": "resend"},
        name="run-email-recipient-resend",
    ),
]
