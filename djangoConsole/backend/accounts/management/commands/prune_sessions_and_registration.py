# FileName: prune_sessions_and_registration.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand
from django.utils import timezone

from operations.models import CleanupTask
from operations.cleanup_status import record_cleanup

from accounts.models import RegistrationToken


class Command(BaseCommand):
    help = (
        "Delete expired browser sessions and organization registration tokens. "
        "Run at least once per hour."
    )
    requires_migrations_checks = True

    def handle(self, *_args: object, **_options: object) -> None:
        with record_cleanup(CleanupTask.SESSIONS_AND_REGISTRATION):
            currentTime = timezone.now()
            intSessionCount, _ = Session.objects.filter(
                expire_date__lte=currentTime
            ).delete()
            intTokenCount, _ = RegistrationToken.objects.filter(
                expires_at__lte=currentTime
            ).delete()

        self.stdout.write(
            f"Deleted {intSessionCount} expired session(s) and {intTokenCount} expired registration token(s)."
        )
