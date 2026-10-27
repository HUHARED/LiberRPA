# FileName: payloads.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from typing import cast

from accounts.models import User
from organizations.access_info import get_department_access_info
from organizations.permissions import OrganizationAccessContext
from runs.models import ExecutorWorkState

from .models import Executor, ExecutorSession
from .queries import ExecutorInfo


def build_executor_work_payload(executorInfo: ExecutorInfo) -> dict[str, object]:
    session = executorInfo.session
    workState = (
        None
        if session is None
        else ExecutorWorkState.objects.filter(
            executor=executorInfo.executor, session_id=session.pk
        ).first()
    )
    return {
        "other_active_run_count": None
        if workState is None
        else workState.other_active_run_count,
        "central_running_count": None
        if workState is None
        else len(workState.running_run_ids),
        "local_waiting_count": None
        if workState is None
        else workState.local_waiting_count,
        "last_work_reported_at": None if workState is None else workState.reported_at,
    }


def build_client_session_payload(
    session: ExecutorSession, access: OrganizationAccessContext
) -> dict[str, object]:
    user = cast(User, session.user)
    tupleDepartmentAccessInfo = get_department_access_info(access)
    executor = cast(Executor | None, session.executor)
    return {
        "session": {
            "id": session.id,
            "selection_required": session.executor_id is None,
            "expires_at": session.expires_at,
        },
        "user": {"id": user.id, "email": user.email, "username": user.username},
        "organization": {"id": access.organization.id, "name": access.organization.name},
        "is_org_admin": access.isOrgAdmin,
        "account_departments": [
            {
                "id": department.id,
                "name": department.name,
                "path": department.path,
                "role": department.role,
            }
            for department in tupleDepartmentAccessInfo
        ],
        "executor": None
        if executor is None
        else {
            "id": executor.id,
            "name": executor.name,
            "department_id": executor.department_id,
            "dispatch_enabled": executor.dispatch_enabled,
        },
        "computer_name": session.computer_name,
        "client_version": session.client_version,
        "last_seen_at": session.last_seen_at,
    }
