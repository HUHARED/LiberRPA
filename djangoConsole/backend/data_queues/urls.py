# FileName: urls.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.urls import path

from . import views, public_views

urlpatterns = [
    path("data-queues/", views.list_or_create_queues, name="data-queues"),
    path("data-queues/<uuid:queueId>/", views.get_or_update_queue, name="data-queue"),
    path(
        "data-queues/<uuid:queueId>/deletion/",
        views.delete_queue_view,
        name="data-queue-deletion",
    ),
    path("data-queues/<uuid:queueId>/items/", views.list_queue_items, name="queue-items"),
    path(
        "data-queues/<uuid:queueId>/items/<uuid:itemId>/",
        views.get_queue_item,
        name="queue-item",
    ),
    path(
        "data-queues/<uuid:queueId>/upload/",
        views.upload_queue_items,
        name="queue-upload",
    ),
    path(
        "data-queues/<uuid:queueId>/reset/", views.reset_queue_items, name="queue-reset"
    ),
    path(
        "data-queues/<uuid:queueId>/delete_items/",
        views.delete_queue_items,
        name="queue-delete_items",
    ),
    path(
        "v1/data-queues/query/",
        public_views.query_queue_items,
        name="public-queue-query",
    ),
    path(
        "v1/data-queues/upload/",
        public_views.upload_queue_items,
        name="public-queue-upload",
    ),
    path(
        "v1/data-queues/claim/",
        public_views.claim_queue_items,
        name="public-queue-claim",
    ),
    path(
        "v1/data-queues/reset/",
        public_views.reset_queue_items,
        name="public-queue-reset",
    ),
    path(
        "v1/data-queues/delete_items/",
        public_views.delete_queue_items,
        name="public-queue-delete_items",
    ),
]
