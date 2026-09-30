# FileName: http.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from typing import cast

from django.contrib.auth import HASH_SESSION_KEY
from django.http import HttpRequest, JsonResponse
from django.views.decorators.debug import sensitive_variables

from accounts.models import User
from accounts.session_revocation import lock_session_write_access
from console_project.http import build_authentication_required_response
from organizations.models import Membership
from organizations.permissions import (
    AccessChannel,
    OrganizationAccessContext,
    get_current_membership,
)

from .models import Executor
from .queries import ExecutorInfo


def get_executor_request_membership(request: HttpRequest) -> Membership | JsonResponse:
    if not request.user.is_authenticated:
        return build_authentication_required_response()
    return get_current_membership(actorId=cast(User, request.user).id)


@sensitive_variables()
def lock_executor_write_access(
    request: HttpRequest, membership: Membership
) -> OrganizationAccessContext:
    """Recheck the initiating Session and lock current access inside the view's transaction."""
    return lock_session_write_access(
        membership.user_id,
        membership.organization_id,
        AccessChannel.SESSION,
        request.session.get(HASH_SESSION_KEY, ""),
        request.session.get_expiry_date(),
    )


def build_executor_payload(executor: Executor) -> dict[str, object]:
    return {
        "id": executor.id,
        "name": executor.name,
        "department_id": executor.department_id,
        "notes": executor.notes,
        "dispatch_enabled": executor.dispatch_enabled,
        "created_at": executor.created_at,
        "deleted_at": executor.deleted_at,
    }


def build_executor_info_payload(executorInfo: ExecutorInfo) -> dict[str, object]:
    session = executorInfo.session
    return {
        **build_executor_payload(executorInfo.executor),
        "department": {
            "id": executorInfo.executor.department_id,
            "name": executorInfo.executor.department.name,
            "path": executorInfo.departmentPath,
        },
        "can_manage": executorInfo.canManage,
        "association_status": executorInfo.associationStatus,
        "session_id": None if session is None else session.id,
        "account": None
        if session is None
        else {
            "id": session.user_id,
            "email": session.user.email,
            "username": session.user.username,
        },
        "computer": None if session is None else session.computer,
        "version": None if session is None else session.client_version,
        "last_seen_at": None if session is None else session.last_seen_at,
    }
