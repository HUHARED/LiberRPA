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

from organizations.permissions import (
    AccessChannel,
    resolve_organization_access,
    require_organization_admin,
)

from .models import AuditScope, AuditRecord

_INT_RECORDS_PER_PAGE = 50


@dataclass(frozen=True)
class AuditListFilters:
    fromTime: datetime | None
    untilTime: datetime | None
    actorIds: tuple[uuid.UUID, ...]
    includeSystem: bool
    modules: tuple[str, ...]
    actions: tuple[str, ...]
    results: tuple[str, ...]


def _get_organization_audit_query(
    actorId: uuid.UUID, organizationId: uuid.UUID, channel: AccessChannel
) -> QuerySet[AuditRecord]:
    access = resolve_organization_access(
        actorId=actorId, organizationId=organizationId, channel=channel
    )
    require_organization_admin(access)
    # A platform record may also carry an organization ID, but it is not tenant history.
    return AuditRecord.objects.filter(
        scope=AuditScope.ORGANIZATION, organization_id=access.organization.id
    )


def get_audit_list(
    *,
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    filters: AuditListFilters,
    pageNumber: int = 1,
) -> Page:
    """Filter authorized history before pagination; HTTP parsing owns filter validation."""
    auditQuery = _get_organization_audit_query(actorId, organizationId, channel)
    if filters.fromTime is not None:
        auditQuery = auditQuery.filter(created_at__gte=filters.fromTime)
    if filters.untilTime is not None:
        auditQuery = auditQuery.filter(created_at__lt=filters.untilTime)
    if filters.actorIds or filters.includeSystem:
        actorCondition = Q(actor_id__in=filters.actorIds)
        if filters.includeSystem:
            actorCondition |= Q(actor_id__isnull=True)
        auditQuery = auditQuery.filter(actorCondition)
    if filters.modules:
        auditQuery = auditQuery.filter(module__in=filters.modules)
    if filters.actions:
        auditQuery = auditQuery.filter(action__in=filters.actions)
    if filters.results:
        auditQuery = auditQuery.filter(result__in=filters.results)
    # Detail bodies are loaded only when opening one record.
    return Paginator(
        auditQuery.defer("details").order_by("-created_at", "-id"),
        _INT_RECORDS_PER_PAGE,
    ).page(pageNumber)


def get_audit_filter_options(
    *, actorId: uuid.UUID, organizationId: uuid.UUID, channel: AccessChannel
) -> dict[str, object]:
    """Offer values present in retained organization history, including deleted accounts."""
    auditQuery = _get_organization_audit_query(actorId, organizationId, channel)
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
    return {
        "actors": [
            {"id": actorId, "name": strActorName if actorId is not None else "System"}
            for actorId, strActorName in actorQuery
        ],
        "modules": list(
            auditQuery.order_by("module").values_list("module", flat=True).distinct()
        ),
        "actions": list(
            auditQuery.order_by("action").values_list("action", flat=True).distinct()
        ),
    }


def get_audit_details(
    *,
    actorId: uuid.UUID,
    organizationId: uuid.UUID,
    channel: AccessChannel,
    auditId: uuid.UUID,
) -> AuditRecord:
    """Read one historical snapshot without querying or linking its current business object."""
    return _get_organization_audit_query(actorId, organizationId, channel).get(pk=auditId)
