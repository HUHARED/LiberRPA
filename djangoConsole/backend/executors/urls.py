# FileName: urls.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.urls import path

from .client_sessions import ExecutorClientAction
from .client_views import (
    process_executor_client_request,
    sign_in_executor,
)
from .group_views import (
    delete_executor_group_record,
    get_or_update_executor_group,
    list_or_create_executor_groups,
)
from .views import (
    change_executor_dispatch,
    delete_executor_record,
    get_or_update_executor,
    list_or_create_executors,
    unassociate_executor_record,
)

urlpatterns = [
    path("executors/", list_or_create_executors, name="executors"),
    path("executors/<uuid:executorId>/", get_or_update_executor, name="executor"),
    path(
        "executors/<uuid:executorId>/dispatch/",
        change_executor_dispatch,
        name="executor-dispatch",
    ),
    path(
        "executors/<uuid:executorId>/deletion/",
        delete_executor_record,
        name="executor-deletion",
    ),
    path(
        "executors/<uuid:executorId>/unassociate/",
        unassociate_executor_record,
        name="executor-unassociate",
    ),
    path("executor-groups/", list_or_create_executor_groups, name="executor-groups"),
    path(
        "executor-groups/<uuid:groupId>/",
        get_or_update_executor_group,
        name="executor-group",
    ),
    path(
        "executor-groups/<uuid:groupId>/deletion/",
        delete_executor_group_record,
        name="executor-group-deletion",
    ),
    path("clients/executor/login/", sign_in_executor, name="executor-client-login"),
    path(
        "clients/executor/choices/",
        process_executor_client_request,
        {"action": ExecutorClientAction.CHOICES},
        name="executor-client-choices",
    ),
    path(
        "clients/executor/associate/",
        process_executor_client_request,
        {"action": ExecutorClientAction.ASSOCIATE},
        name="executor-client-associate",
    ),
    path(
        "clients/executor/session/",
        process_executor_client_request,
        {"action": ExecutorClientAction.SESSION},
        name="executor-client-session",
    ),
    path(
        "clients/executor/heartbeat/",
        process_executor_client_request,
        {"action": ExecutorClientAction.HEARTBEAT},
        name="executor-client-heartbeat",
    ),
    path(
        "clients/executor/logout/",
        process_executor_client_request,
        {"action": ExecutorClientAction.LOGOUT},
        name="executor-client-logout",
    ),
]
