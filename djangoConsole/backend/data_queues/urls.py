# FileName: urls.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.urls import path

from .views import public_queue_request, queue_request

urlpatterns = [
    path("data-queues/", queue_request, {"action": "list"}, name="data-queues"),
    path(
        "data-queues/<uuid:queueId>/",
        queue_request,
        {"action": "details"},
        name="data-queue",
    ),
    path(
        "data-queues/<uuid:queueId>/deletion/",
        queue_request,
        {"action": "delete_queue"},
        name="data-queue-deletion",
    ),
    path(
        "data-queues/<uuid:queueId>/items/",
        queue_request,
        {"action": "items"},
        name="queue-items",
    ),
    path(
        "data-queues/<uuid:queueId>/items/<uuid:itemId>/",
        queue_request,
        {"action": "item"},
        name="queue-item",
    ),
    *[
        path(
            f"data-queues/<uuid:queueId>/{action}/",
            queue_request,
            {"action": action},
            name=f"queue-{action}",
        )
        for action in ("upload", "reset", "delete_items")
    ],
    *[
        path(
            f"v1/data-queues/{action}/",
            public_queue_request,
            {"action": action},
            name=f"public-queue-{action}",
        )
        for action in ("query", "upload", "claim", "reset", "delete_items")
    ],
]
