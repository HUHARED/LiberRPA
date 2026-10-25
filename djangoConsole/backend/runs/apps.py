# FileName: apps.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.apps import AppConfig


class RunsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "runs"

    def ready(self) -> None:
        # Register execution invalidations after every application's models are loaded.
        from . import browser_events  # noqa: F401
