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

from .models import AuditScope, AuditChannel, AuditResult, AuditRecord

_LOGGER = logging.getLogger("console.audit")
# These are write endpoints. Anonymous authentication failures stay in runtime diagnostics;
# a supplied email or bearer value must never be treated as an authenticated audit actor.
_DICT_WRITE_ACTION = {
    "auth-profile": "account.update_profile",
    "auth-api-keys": "api_key.create",
    "auth-api-key-notes": "api_key.update",
    "auth-api-key-revoke": "api_key.revoke",
    "organization-member-api-key-revoke": "api_key.revoke",
    "auth-account-deletion": "account.delete",
    "organization-member-deletion": "account.delete",
    "auth-password-change": "account.change_password",
    "auth-logout-others": "account.revoke_sessions",
    "email-change-email": "account.request_email_change",
    "organization-settings": "organization.update",
    "organization-deletion": "organization.schedule_deletion",
    "organization-deletion-cancel": "organization.cancel_deletion",
    "organization-departments": "department.create",
    "organization-department": "department.update",
    "organization-department-deletion": "department.delete",
    "organization-member": "membership.update",
    "organization-invitations": "invitation.create",
    "organization-invitation-resend": "invitation.resend",
    "organization-invitation-revoke": "invitation.revoke",
    "executors": "executor.create",
    "executor": "executor.update",
    "executor-dispatch": "executor.set_dispatch",
    "executor-deletion": "executor.delete",
    "executor-unassociate": "executor.unassociate",
    "executor-groups": "executor_group.create",
    "executor-group": "executor_group.update",
    "executor-group-deletion": "executor_group.delete",
}


def record_failed_request(request: HttpRequest, response: HttpResponseBase) -> None:
    """Record authenticated write failures after the view's business transaction ended."""
    if (
        request.method != "POST"
        or response.status_code < 400
        or not request.resolver_match
    ):
        return
    strAction = _DICT_WRITE_ACTION.get(request.resolver_match.url_name or "")
    if strAction is None:
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
                "stage": "request",
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
            strModule = strAction.split(".")[0]
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
                action=strAction,
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
