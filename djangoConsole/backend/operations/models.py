# FileName: models.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.db import models


class ServiceSettings(models.Model):
    """One shared settings record for the Console instance, independent of any organization."""

    # This fixed key identifies the singleton settings row, not a business resource.
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    allow_organization_creation = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(id=1),
                name="service_settings_singleton",
                violation_error_message="The Console instance can have only one service settings record.",
            )
        ]

    def __str__(self) -> str:
        return "Console service settings"
