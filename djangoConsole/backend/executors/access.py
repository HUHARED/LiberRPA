# FileName: access.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from datetime import datetime

from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views.decorators.debug import sensitive_variables

from accounts.models import User
from accounts.session_revocation import SessionInvalidatedError
from organizations.models import DepartmentRole
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
    get_authorized_departments,
    resolve_organization_access,
)


@sensitive_variables()
def lock_executor_write_access(
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    sessionAuthHash: str,
    sessionExpiresAt: datetime,
) -> OrganizationAccessContext:
    """Keep Executor and group writes in the same account and organization lock order."""
    if channel != AccessChannel.SESSION:
        raise PermissionDenied(
            "A signed-in account is required to manage Executors and groups."
        )
    access = resolve_organization_access(
        actorId=actorId, organizationId=organizationId, channel=channel, forUpdate=True
    )
    # Recheck after the locks; a waiting write cannot reuse an expired or revoked session.
    actor = User.objects.get(pk=actorId)
    if (
        sessionExpiresAt <= timezone.now()
        or not sessionAuthHash
        or not constant_time_compare(sessionAuthHash, actor.get_session_auth_hash())
    ):
        raise SessionInvalidatedError("The current session is no longer valid.")
    return access


def require_executor_management(
    access: OrganizationAccessContext, departmentId: uuid.UUID
) -> None:
    if (
        not get_authorized_departments(access, requiredRole=DepartmentRole.DEVELOPER)
        .filter(pk=departmentId)
        .exists()
    ):
        raise PermissionDenied(
            "Developer access is required to manage Executors and groups."
        )
