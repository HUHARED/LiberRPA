# FileName: http.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from datetime import datetime
from typing import TypedDict, cast

from django.contrib.auth import HASH_SESSION_KEY
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from accounts.models import User
from console_project.http import build_error_response
from organizations.models import Membership
from organizations.permissions import AccessChannel, get_current_membership

from .models import Executor
from .queries import ExecutorInfo
from .session_state import get_executor_association_status


class ExecutorWriteContext(TypedDict):
    actorId: uuid.UUID
    organizationId: uuid.UUID
    channel: AccessChannel
    sessionAuthHash: str
    sessionExpiresAt: datetime


def get_executor_request_membership(request: HttpRequest) -> Membership | JsonResponse:
    if not request.user.is_authenticated:
        return build_error_response(
            "authentication_required", "Sign in to continue.", statusCode=401
        )
    return get_current_membership(actorId=cast(User, request.user).id)


@sensitive_variables()
def get_executor_write_context(
    request: HttpRequest, membership: Membership
) -> ExecutorWriteContext:
    return {
        "actorId": membership.user_id,
        "organizationId": membership.organization_id,
        "channel": AccessChannel.SESSION,
        "sessionAuthHash": request.session.get(HASH_SESSION_KEY, ""),
        "sessionExpiresAt": request.session.get_expiry_date(),
    }


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
    associationStatus = get_executor_association_status(
        session, currentTime=timezone.now()
    )
    return {
        **build_executor_payload(executorInfo.executor),
        "department": {
            "id": executorInfo.executor.department_id,
            "name": executorInfo.executor.department.name,
            "path": executorInfo.departmentPath,
        },
        "can_manage": executorInfo.canManage,
        "association_status": associationStatus,
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
