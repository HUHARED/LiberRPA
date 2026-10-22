# FileName: audit_queries.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from dataclasses import dataclass
from datetime import datetime

from django.core.paginator import Page, Paginator
from django.db.models import F, Q, QuerySet, Window
from django.db.models.functions import RowNumber

from console_project.constants import INT_LIST_PAGE_SIZE

from .audit_contracts import AuditAction, AuditResult
from .models import AuditRecord


@dataclass(frozen=True)
class AuditListFilters:
    fromTime: datetime | None
    untilTime: datetime | None
    actorIds: tuple[uuid.UUID, ...]
    includeSystem: bool
    modules: tuple[str, ...]
    actions: tuple[AuditAction, ...]
    results: tuple[AuditResult, ...]
    organizationIds: tuple[uuid.UUID, ...] = ()
    includeInstance: bool = False


def get_audit_list(
    *,
    auditQuery: QuerySet[AuditRecord],
    filters: AuditListFilters,
    pageNumber: int = 1,
) -> Page:
    """Filter authorized history before pagination; HTTP parsing owns filter validation."""
    if filters.fromTime is not None:
        auditQuery = auditQuery.filter(created_at__gte=filters.fromTime)
    if filters.untilTime is not None:
        auditQuery = auditQuery.filter(created_at__lt=filters.untilTime)
    if filters.actorIds or filters.includeSystem:
        actorCondition = Q(actor_id__in=filters.actorIds)
        if filters.includeSystem:
            actorCondition |= Q(actor_id__isnull=True)
        auditQuery = auditQuery.filter(actorCondition)
    if filters.organizationIds or filters.includeInstance:
        organizationCondition = Q(organization_id__in=filters.organizationIds)
        if filters.includeInstance:
            organizationCondition |= Q(organization_id__isnull=True)
        auditQuery = auditQuery.filter(organizationCondition)
    if filters.modules:
        auditQuery = auditQuery.filter(module__in=filters.modules)
    if filters.actions:
        auditQuery = auditQuery.filter(action__in=filters.actions)
    if filters.results:
        auditQuery = auditQuery.filter(result__in=filters.results)
    # Detail bodies are loaded only when opening one record.
    return Paginator(
        auditQuery.defer("details").order_by("-created_at", "-id"),
        INT_LIST_PAGE_SIZE,
    ).page(pageNumber)


def get_audit_filter_options(
    *, auditQuery: QuerySet[AuditRecord], platform: bool = False
) -> dict[str, object]:
    """Offer retained snapshots from an already authorized query, including deleted identities."""
    # Pick the latest recorded name for each actor without consulting current account names.
    actorQuery = (
        auditQuery
        .annotate(
            actorPosition=Window(
                expression=RowNumber(),
                partition_by=[F("actor_id")],
                order_by=[F("created_at").desc(), F("id").desc()],
            )
        )
        .filter(actorPosition=1)
        .order_by("actor_name", "actor_id")
        .values_list("actor_id", "actor_name")
    )
    dictOptions: dict[str, object] = {
        "actors": [
            {"id": actorId, "name": strActorName if actorId is not None else "System"}
            for actorId, strActorName in actorQuery
        ],
        "actions": list(
            auditQuery.order_by("action").values_list("action", flat=True).distinct()
        ),
    }

    if platform:
        organizationQuery = (
            auditQuery
            .annotate(
                organizationPosition=Window(
                    expression=RowNumber(),
                    partition_by=[F("organization_id")],
                    order_by=[F("created_at").desc(), F("id").desc()],
                )
            )
            .filter(organizationPosition=1)
            .order_by("organization_name", "organization_id")
            .values_list("organization_id", "organization_name")
        )
        dictOptions["organizations"] = [
            {"id": organizationId, "name": strOrganizationName}
            for organizationId, strOrganizationName in organizationQuery
        ]
    else:
        dictOptions["modules"] = list(
            auditQuery.order_by("module").values_list("module", flat=True).distinct()
        )
    return dictOptions
