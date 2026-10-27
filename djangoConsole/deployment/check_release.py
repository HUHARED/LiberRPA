# FileName: check_release.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import sys
from pathlib import Path

import django
from django.apps import apps
from django.conf import settings
from django.core.management import call_command


def main() -> None:
    """Check migration files without loading instance configuration or using a database."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
    from console_project.model_settings import INSTALLED_APPS, AUTH_USER_MODEL

    settings.configure(INSTALLED_APPS=INSTALLED_APPS, AUTH_USER_MODEL=AUTH_USER_MODEL)
    django.setup()
    # Explicit app labels also detect applications whose migration files are all missing.
    listAppLabel = [appConfig.label for appConfig in apps.get_app_configs()]
    call_command("makemigrations", *listAppLabel, check=True, interactive=False)


if __name__ == "__main__":
    main()
