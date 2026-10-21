# FileName: audit_http.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import json
import logging
import re
import uuid

from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, transaction
from django.http import HttpRequest, HttpResponse, HttpResponseBase

from console_project.logging import get_request_id
from organizations.models import Organization, Membership

from .contracts import AuditAction, AuditChannel, AuditResult, AuditStage
from .models import AuditScope, AuditRecord

_LOGGER = logging.getLogger("console.audit")
# These are write endpoints. Anonymous authentication failures stay in runtime diagnostics;
# a supplied email or bearer value must never be treated as an authenticated audit actor.
_DICT_WRITE_ACTION: dict[str, AuditAction] = {
    "auth-profile": AuditAction.ACCOUNT_UPDATE_PROFILE,
    "auth-api-keys": AuditAction.API_KEY_CREATE,
    "auth-api-key-notes": AuditAction.API_KEY_UPDATE,
    "auth-api-key-revoke": AuditAction.API_KEY_REVOKE,
    "organization-member-api-key-revoke": AuditAction.API_KEY_REVOKE,
    "auth-account-deletion": AuditAction.ACCOUNT_DELETE,
    "organization-member-deletion": AuditAction.ACCOUNT_DELETE,
    "auth-password-change": AuditAction.ACCOUNT_CHANGE_PASSWORD,
    "auth-logout-others": AuditAction.ACCOUNT_REVOKE_SESSIONS,
    "email-change-email": AuditAction.ACCOUNT_REQUEST_EMAIL_CHANGE,
    "organization-settings": AuditAction.ORGANIZATION_UPDATE,
    "organization-deletion": AuditAction.ORGANIZATION_SCHEDULE_DELETION,
    "organization-deletion-cancel": AuditAction.ORGANIZATION_CANCEL_DELETION,
    "organization-departments": AuditAction.DEPARTMENT_CREATE,
    "organization-department": AuditAction.DEPARTMENT_UPDATE,
    "organization-department-deletion": AuditAction.DEPARTMENT_DELETE,
    "organization-member": AuditAction.MEMBERSHIP_UPDATE,
    "organization-invitations": AuditAction.INVITATION_CREATE,
    "organization-invitation-resend": AuditAction.INVITATION_RESEND,
    "organization-invitation-revoke": AuditAction.INVITATION_REVOKE,
    "executors": AuditAction.EXECUTOR_CREATE,
    "executor": AuditAction.EXECUTOR_UPDATE,
    "executor-dispatch": AuditAction.EXECUTOR_SET_DISPATCH,
    "executor-deletion": AuditAction.EXECUTOR_DELETE,
    "executor-unassociate": AuditAction.EXECUTOR_UNASSOCIATE,
    "executor-groups": AuditAction.EXECUTOR_GROUP_CREATE,
    "executor-group": AuditAction.EXECUTOR_GROUP_UPDATE,
    "executor-group-deletion": AuditAction.EXECUTOR_GROUP_DELETE,
    "assets": AuditAction.ASSET_CREATE,
    "asset": AuditAction.ASSET_UPDATE,
    "asset-deletion": AuditAction.ASSET_DELETE,
}


def record_failed_request(request: HttpRequest, response: HttpResponseBase) -> None:
    """Record business failures; rate refusals stay in runtime diagnostics without audit writes."""
    if (
        request.method != "POST"
        or response.status_code < 400
        or not request.resolver_match
        or response.status_code == 429
    ):
        return
    auditAction = _DICT_WRITE_ACTION.get(request.resolver_match.url_name or "")
    if auditAction is None:
        return
    try:
        with transaction.atomic():
            user = getattr(request, "user", None)
            if user is None or not user.is_authenticated:
                return
            membership = (
                Membership.objects
                .select_related("organization", "user")
                .filter(user_id=user.pk)
                .first()
            )
            if membership is None:
                return
            if (
                not Organization.objects
                .select_for_update()
                .filter(pk=membership.organization_id)
                .exists()
            ):
                return
            # The scope comes from the authenticated actor, never a target ID or posted organization.
            dictDetail: dict[str, object] = {
                "stage": AuditStage.REQUEST,
                "http_status": response.status_code,
            }
            if isinstance(response, HttpResponse) and len(response.content) <= 32768:
                try:
                    strCode = json.loads(response.content).get("error", {}).get("code")
                    if isinstance(strCode, str) and re.fullmatch(
                        r"[a-z_]{1,64}", strCode
                    ):
                        dictDetail["reason_code"] = strCode
                except (ValueError, AttributeError, TypeError):
                    pass
            strObjectId = next(
                (
                    str(request.resolver_match.kwargs[strParameter])
                    for strParameter in (
                        "apiKeyId",
                        "assetId",
                        "departmentId",
                        "executorId",
                        "groupId",
                        "invitationId",
                        "userId",
                    )
                    if isinstance(
                        request.resolver_match.kwargs.get(strParameter), uuid.UUID
                    )
                ),
                "",
            )
            strModule = auditAction.split(".")[0]
            if not strObjectId and strModule in ("account", "organization"):
                strObjectId = str(
                    membership.user_id
                    if strModule == "account"
                    else membership.organization_id
                )
            strObjectType = {"account": "user", "invitation": "memberinvitation"}.get(
                strModule, strModule.replace("_", "")
            )
            AuditRecord.objects.create(
                scope=AuditScope.ORGANIZATION,
                organization_id=membership.organization_id,
                organization_name=membership.organization.name,
                actor_id=membership.user_id,
                actor_name=str(membership.user),
                channel=AuditChannel.SESSION,
                request_id=get_request_id(),
                module=strModule,
                action=auditAction,
                object_type=strObjectType,
                object_id=strObjectId,
                object_name="",
                result=AuditResult.FAILED,
                details=dictDetail,
            )
    except (DatabaseError, ImproperlyConfigured):
        # A database outage cannot itself be recorded in that database.
        # Preserve the original HTTP response and emit correlated diagnostics instead.
        _LOGGER.exception("Failed request audit could not be saved.")
