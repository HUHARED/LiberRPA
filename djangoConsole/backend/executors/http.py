# FileName: http.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from runs.models import ExecutorWorkState

from .models import Executor
from .queries import ExecutorInfo


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
        "computer_name": None if session is None else session.computer_name,
        "client_version": None if session is None else session.client_version,
        "last_seen_at": None if session is None else session.last_seen_at,
    }


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
