# FileName: policies.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.core.exceptions import PermissionDenied

from .models import ServiceSettings


def require_organization_creation_allowed() -> None:
    """Check the current creation policy and hold its row lock until the caller commits.

    The caller must already be inside the registration transaction.
    Reading this policy does not authorize platform settings changes.
    """
    # The first use creates the shared default row; later calls preserve its saved value.
    serviceSettings, _ = ServiceSettings.objects.select_for_update().get_or_create(pk=1)
    if not serviceSettings.allow_organization_creation:
        raise PermissionDenied("Organization creation is currently disabled.")
