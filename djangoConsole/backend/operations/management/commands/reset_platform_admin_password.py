# FileName: reset_platform_admin_password.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.views.decorators.debug import sensitive_variables

from console_project.terminal import PasswordInputError, read_password
from accounts.models import User
from accounts.password_changes import save_password_change
from accounts.passwords import validate_new_password
from operations.contracts import AuditAction
from operations.audit import record_audit


class Command(BaseCommand):
    help = "Reset the sole platform administrator's password and invalidate its sessions."
    requires_migrations_checks = True

    @sensitive_variables()
    def handle(self, *_args: object, **_options: object) -> None:
        if not User.objects.filter(is_platform_admin=True).exists():
            raise CommandError(
                "Run initialize_console to create the platform administrator."
            )

        try:
            strPassword = read_password("New password: ")
            if strPassword != read_password("New password again: "):
                raise CommandError("The passwords do not match.")
        except (EOFError, KeyboardInterrupt):
            raise CommandError("Password reset cancelled.") from None
        except PasswordInputError as e:
            raise CommandError(str(e)) from None

        try:
            with transaction.atomic():
                user = User.objects.select_for_update().get(is_platform_admin=True)
                validate_new_password(strPassword, user)
                user.set_password(strPassword)
                save_password_change(user)
                record_audit(
                    AuditAction.PLATFORM_RESET_PASSWORD,
                    actor=None,
                    organization=None,
                    target=user,
                )
        except ValidationError as e:
            raise CommandError(" ".join(e.messages)) from None

        self.stdout.write(self.style.SUCCESS("Platform administrator password reset."))
