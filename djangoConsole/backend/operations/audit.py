# FileName: audit.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import json
import re
from collections.abc import Iterable
from typing import cast

from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, models
from django.views.decorators.debug import sensitive_variables

from accounts.models import User
from console_project.logging import get_request_id
from executors.models import ExecutorGroupMember
from organizations.models import (
    Organization,
    Membership,
    DepartmentMembership,
    InvitationDepartmentRole,
)
from organizations.permissions import AccessChannel

from .contracts import AuditChannel, AuditResult, AuditStage
from .models import ServiceSettings, MaintenanceState, AuditScope, AuditRecord
from .backup_models import BackupRecord

_INT_MAX_OBJECT_NAME_LENGTH = cast(
    models.CharField, AuditRecord._meta.get_field("object_name")
).max_length
_INT_MAX_DETAIL_BYTES = 4096
# Each model explicitly opts safe metadata into history. Never serialize a complete model.
_DICT_SNAPSHOT_FIELD = {
    "accounts.user": ("username", "email", "time_zone"),
    "accounts.apikey": ("name", "user_id", "expires_at", "revoked_at", "notes"),
    "accounts.editorsession": ("user_id", "computer_name", "client_version"),
    "organizations.organization": (
        "name",
        "default_time_zone",
        "notes",
        "run_log_retention_days",
        "suspended_at",
        "deletion_requested_at",
        "deletion_due_at",
        "deletion_started_at",
    ),
    "organizations.membership": ("is_org_admin", "notes"),
    "organizations.department": ("name", "parent_id", "notes", "deleted_at"),
    "organizations.memberinvitation": (
        "email",
        "is_org_admin",
        "notes",
        "expires_at",
        "revoked_at",
        "accepted_at",
    ),
    "executors.executor": (
        "name",
        "department_id",
        "notes",
        "dispatch_enabled",
        "deleted_at",
    ),
    "executors.executorgroup": ("name", "department_id", "notes", "deleted_at"),
    "executors.executorsession": (
        "user_id",
        "executor_id",
        "computer_name",
        "client_version",
    ),
    "assets.asset": ("name", "department_id", "asset_type", "notes"),
    "data_queues.dataqueue": ("name", "department_id", "notes"),
    "shared_files.sharedfile": ("name", "department_id", "blob_id"),
    "operations.servicesettings": ("allow_organization_creation",),
    "operations.maintenancestate": ("entered_at",),
    "schedules.schedule": (
        "name",
        "department_id",
        "package_id",
        "cron",
        "time_zone",
        "active_from",
        "active_until",
        "enabled",
        "notes",
        "deleted_at",
        "group_id",
        "executor_ids",
    ),
}


@sensitive_variables()
def get_audit_snapshot(target: models.Model) -> dict[str, object]:
    """Capture selected metadata before a write; Notes content is never persisted."""
    strLabel = target._meta.label_lower
    dictSnapshot = {
        strField: getattr(target, strField) for strField in _DICT_SNAPSHOT_FIELD[strLabel]
    }
    match strLabel:
        case "organizations.membership":
            dictSnapshot["department_roles"] = {
                str(departmentId): strRole
                for departmentId, strRole in DepartmentMembership.objects
                .filter(membership_id=target.pk)
                .order_by("department_id")
                .values_list("department_id", "role")
            }
        case "organizations.memberinvitation":
            dictSnapshot["department_roles"] = {
                str(departmentId): strRole
                for departmentId, strRole in InvitationDepartmentRole.objects
                .filter(invitation_id=target.pk)
                .order_by("department_id")
                .values_list("department_id", "role")
            }
        case "executors.executorgroup":
            dictSnapshot["executor_ids"] = list(
                ExecutorGroupMember.objects
                .filter(group_id=target.pk)
                .order_by("executor_id")
                .values_list("executor_id", flat=True)
            )
    return dictSnapshot


def _build_changes(
    before: dict[str, object], after: dict[str, object]
) -> dict[str, object]:
    dictChange: dict[str, object] = {}
    for strField, afterValue in after.items():
        beforeValue = before.get(strField)
        if strField == "notes" and not beforeValue and not afterValue:
            continue
        if beforeValue != afterValue:
            dictChange[strField] = (
                {"changed": True}
                if strField == "notes"
                else {"before": beforeValue, "after": afterValue}
            )
    return dictChange


def _bound_details(details: dict[str, object]) -> dict[str, object]:
    strDetails = json.dumps(
        details, cls=DjangoJSONEncoder, ensure_ascii=False, separators=(",", ":")
    )
    if len(strDetails.encode("utf-8")) > _INT_MAX_DETAIL_BYTES:
        # Large role/member changes keep field names and an explicit omission marker.
        return {
            "stage": details.get("stage", AuditStage.OPERATION),
            "changed_fields": list(cast(dict, details.get("changes", {}))),
            "details_omitted": True,
        }
    return cast(dict[str, object], json.loads(strDetails))


@sensitive_variables()
def _build_audit_record(
    action: str,
    *,
    actor: User | None,
    organization: Organization | None,
    target: models.Model,
    channel: AuditChannel | AccessChannel = AuditChannel.SESSION,
    before: dict[str, object] | None = None,
    scope: AuditScope | None = None,
    metadata: dict[str, object] | None = None,
    stage: AuditStage = AuditStage.OPERATION,
    result: AuditResult = AuditResult.SUCCEEDED,
) -> AuditRecord | None:
    """Build verified identity snapshots in the caller's business transaction.

    The caller supplies the authenticated actor and the operation's organization.
    Organization operations must already hold its lock, or have created it in this transaction.
    Registration, recovery, logout, and system cleanup retain their own authorization rules.
    This function neither resolves identity nor acquires business locks; audit failures propagate.
    """
    if not connection.in_atomic_block:
        raise RuntimeError(
            "Write successful audit records inside the business transaction."
        )
    if re.fullmatch(r"[a-z_]+\.[a-z_]+", action) is None:
        raise ValueError("Use a controlled module.action audit name.")
    if channel not in AuditChannel.values:
        raise ValueError("Unknown audit channel.")
    dictChange = (
        {} if before is None else _build_changes(before, get_audit_snapshot(target))
    )
    if before is not None and not dictChange and not metadata:
        return
    strObjectName = (
        str(target.user)
        if isinstance(target, Membership)
        else str(target)
        if isinstance(target, (User, ServiceSettings, MaintenanceState, BackupRecord))
        else str(getattr(target, "name", getattr(target, "email", target.pk)))
    )
    return AuditRecord(
        scope=scope
        or (AuditScope.ORGANIZATION if organization is not None else AuditScope.PLATFORM),
        organization_id=organization.pk if organization is not None else None,
        organization_name=organization.name if organization is not None else "",
        actor_id=actor.pk if actor is not None else None,
        actor_name=str(actor) if actor is not None else "System",
        channel=AuditChannel.SYSTEM if actor is None else channel,
        request_id=get_request_id(),
        module=action.split(".")[0],
        action=action,
        object_type=target._meta.model_name,
        object_id=str(target.pk),
        object_name=strObjectName[:_INT_MAX_OBJECT_NAME_LENGTH],
        department_id=target.pk
        if target._meta.label_lower == "organizations.department"
        else getattr(target, "department_id", None),
        result=result,
        details=_bound_details({
            "stage": stage,
            "changes": dictChange,
            **({"metadata": metadata} if metadata else {}),
        }),
    )


@sensitive_variables()
def record_audit(
    action: str,
    *,
    actor: User | None,
    organization: Organization | None,
    target: models.Model,
    channel: AuditChannel | AccessChannel = AuditChannel.SESSION,
    before: dict[str, object] | None = None,
    scope: AuditScope | None = None,
    metadata: dict[str, object] | None = None,
    stage: AuditStage = AuditStage.OPERATION,
    result: AuditResult = AuditResult.SUCCEEDED,
) -> None:
    auditRecord = _build_audit_record(
        action,
        actor=actor,
        organization=organization,
        target=target,
        channel=channel,
        before=before,
        scope=scope,
        metadata=metadata,
        stage=stage,
        result=result,
    )
    if auditRecord is not None:
        auditRecord.save(force_insert=True)


@sensitive_variables()
def record_audit_batch(
    action: str,
    *,
    actor: User | None,
    organization: Organization | None,
    targets: Iterable[models.Model],
    channel: AuditChannel | AccessChannel = AuditChannel.SESSION,
) -> None:
    """Preserve one audit record per target without one database write per target."""
    listAuditRecord = []
    for target in targets:
        auditRecord = _build_audit_record(
            action, actor=actor, organization=organization, target=target, channel=channel
        )
        if auditRecord is not None:
            listAuditRecord.append(auditRecord)
    AuditRecord.objects.bulk_create(listAuditRecord, batch_size=500)
