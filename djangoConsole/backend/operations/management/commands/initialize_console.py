# FileName: initialize_console.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.views.decorators.debug import sensitive_variables

from console_project.terminal import PasswordInputError, read_password
from accounts.models import STR_PLATFORM_ADMIN_LOGIN, User
from accounts.passwords import validate_new_password
from operations.contracts import AuditAction
from operations.audit import record_audit


class Command(BaseCommand):
    help = "Create the sole platform administrator after configuring Console and migrating its database."
    requires_migrations_checks = True

    @sensitive_variables()
    def handle(self, *_args: object, **_options: object) -> None:
        if User.objects.filter(is_platform_admin=True).exists():
            raise CommandError("Console already has a platform administrator.")

        try:
            user = User(
                platform_login=STR_PLATFORM_ADMIN_LOGIN,
                username="Platform Administrator",
                is_platform_admin=True,
            )
            user.full_clean(
                exclude=["password"], validate_unique=False, validate_constraints=False
            )

            strPassword = read_password("Password: ")
            if strPassword != read_password("Password again: "):
                raise CommandError("The passwords do not match.")
            validate_new_password(strPassword, user)
            user.set_password(strPassword)
        except (EOFError, KeyboardInterrupt):
            raise CommandError("Initialization cancelled.") from None
        except PasswordInputError as e:
            raise CommandError(str(e)) from None
        except ValidationError as e:
            raise CommandError(" ".join(e.messages)) from None

        try:
            with transaction.atomic():
                if User.objects.filter(is_platform_admin=True).exists():
                    raise CommandError("Console already has a platform administrator.")
                user.save(force_insert=True)
                record_audit(
                    AuditAction.PLATFORM_INITIALIZE,
                    actor=None,
                    organization=None,
                    target=user,
                )
        except IntegrityError:
            if User.objects.filter(is_platform_admin=True).exists():
                raise CommandError(
                    "Console already has a platform administrator."
                ) from None
            raise

        self.stdout.write(
            self.style.SUCCESS(
                f"Platform administrator '{STR_PLATFORM_ADMIN_LOGIN}' created."
            )
        )
