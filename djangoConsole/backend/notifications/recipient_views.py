# FileName: recipient_views.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from accounts.rate_limits import (
    apply_sensitive_action_rate_limit,
    apply_email_token_rate_limit,
)
from console_project.http import build_rate_limited_response, parse_json_request
from operations.audit_contracts import AuditAction
from operations.audit import record_audit
from organizations.http import get_request_membership, lock_request_write_access
from organizations.models import Organization
from organizations.permissions import (
    AccessChannel,
    build_organization_access,
    require_organization_admin,
)
from organizations.rate_limits import RequestBudget, request_budget

from .contracts import (
    RecipientCreationRequest,
    RecipientNotesRequest,
    EmptyRequest,
    RecipientTokenRequest,
    RunEmailRecipientStatus,
)
from .http import handle_notification_errors
from .models import RunEmailRecipient
from .recipients import (
    get_recipient_query,
    get_eligible_recipients,
    create_recipient,
    resend_recipient_verification,
    get_recipient_references,
    delete_recipient,
    load_verification_recipient,
)
from .run_email import get_template_metadata

# Allow 2,000 JSON-escaped Unicode characters, the email address and JSON structure.
_INT_MAX_RECIPIENT_BODY_BYTES = 32 * 1024


def _recipient_payload(recipient: RunEmailRecipient) -> dict:
    return {
        "id": recipient.pk,
        "email": recipient.email,
        "notes": recipient.notes,
        "created_at": recipient.created_at,
        "status": recipient.status,
        "verified_at": recipient.verified_at,
    }


@never_cache
@require_http_methods(["GET", "POST"])
@handle_notification_errors
def list_or_create_recipients(request: HttpRequest) -> JsonResponse:
    membership = get_request_membership(request)
    if isinstance(membership, JsonResponse):
        return membership
    if request.method == "POST":
        form = parse_json_request(
            request, RecipientCreationRequest, maxBodyBytes=_INT_MAX_RECIPIENT_BODY_BYTES
        )
        if isinstance(form, JsonResponse):
            return form
        intRetry = apply_sensitive_action_rate_limit(
            request.META.get("REMOTE_ADDR", ""),
            actorId=str(membership.user_id),
            scope="run_recipient_email",
        )
        if intRetry:
            return build_rate_limited_response(intRetry)
        with transaction.atomic():
            access = lock_request_write_access(request, membership)
            recipient = create_recipient(access, email=form.email, notes=form.notes)
            return JsonResponse({"recipient": _recipient_payload(recipient)}, status=201)
    access = build_organization_access(membership, channel=AccessChannel.SESSION)
    strStatus = request.GET.get("status", "all")
    if strStatus not in ("all", "eligible", *RunEmailRecipientStatus):
        raise ValidationError(
            "Use all, eligible, member, pending, or verified for the status filter."
        )
    query = (
        get_eligible_recipients(access.organization.pk)
        if not access.isOrgAdmin or strStatus == "eligible"
        else get_recipient_query(access.organization.pk)
    )
    if strStatus in RunEmailRecipientStatus:
        query = query.filter(status=strStatus)
    if request.GET.get("email"):
        query = query.filter(email__icontains=request.GET["email"][:254])
    return JsonResponse({
        "recipients": [
            _recipient_payload(recipient) for recipient in query.order_by("email", "id")
        ],
        "can_manage": access.isOrgAdmin,
    })


@never_cache
@require_POST
@handle_notification_errors
def change_recipient(
    request: HttpRequest, recipientId: uuid.UUID, action: str
) -> JsonResponse:
    membership = get_request_membership(request)
    if isinstance(membership, JsonResponse):
        return membership
    if action == "notes":
        form = parse_json_request(
            request, RecipientNotesRequest, maxBodyBytes=_INT_MAX_RECIPIENT_BODY_BYTES
        )
    else:
        form = parse_json_request(request, EmptyRequest)
    if isinstance(form, JsonResponse):
        return form
    if action == "resend":
        intRetry = apply_sensitive_action_rate_limit(
            request.META.get("REMOTE_ADDR", ""),
            actorId=str(membership.user_id),
            scope="run_recipient_email",
        )
        if intRetry:
            return build_rate_limited_response(intRetry)
    with transaction.atomic():
        access = lock_request_write_access(request, membership)
        require_organization_admin(access)
        recipient = (
            get_recipient_query(access.organization.pk)
            .select_for_update()
            .get(pk=recipientId)
        )
        if isinstance(form, RecipientNotesRequest):
            if "\x00" in form.notes:
                raise ValidationError({"notes": "Notes cannot contain null characters."})
            recipient.notes = form.notes
            recipient.save(update_fields=["notes"])
        elif action == "resend":
            resend_recipient_verification(
                recipient, organizationName=access.organization.name
            )
        else:
            listReference = get_recipient_references(recipient)
            if listReference:
                return JsonResponse(
                    {
                        "error": {
                            "code": "recipient_referenced",
                            "message": "This email address is still in use.",
                            "references": listReference,
                        }
                    },
                    status=409,
                )
            record_audit(
                AuditAction.RUN_EMAIL_RECIPIENT_DELETE,
                actor=access.actor,
                organization=access.organization,
                target=recipient,
            )
            delete_recipient(recipient)
            return JsonResponse({"message": "Email address deleted."})
        record_audit(
            AuditAction.RUN_EMAIL_RECIPIENT_NOTES
            if isinstance(form, RecipientNotesRequest)
            else AuditAction.RUN_EMAIL_RECIPIENT_RESEND,
            actor=access.actor,
            organization=access.organization,
            target=recipient,
        )
        return JsonResponse({"recipient": _recipient_payload(recipient)})


@request_budget(RequestBudget.INDEPENDENT)
@never_cache
@require_http_methods(["GET", "POST"])
@handle_notification_errors
def verify_recipient(request: HttpRequest) -> JsonResponse:
    if request.method == "POST":
        form = parse_json_request(request, RecipientTokenRequest)
        if isinstance(form, JsonResponse):
            return form
        strToken = form.token
    else:
        strToken = request.GET.get("token", "")
        if not strToken or len(strToken) > 1000:
            raise ValidationError("The confirmation link is invalid.")
    intRetry = apply_email_token_rate_limit(
        request.META.get("REMOTE_ADDR", ""), token=strToken, scope="run_recipient_token"
    )
    if intRetry:
        return build_rate_limited_response(intRetry)
    recipient = load_verification_recipient(strToken)
    if request.method == "POST":
        with transaction.atomic():
            Organization.objects.select_for_update().get(pk=recipient.organization_id)
            recipient = load_verification_recipient(strToken, forUpdate=True)
            if recipient.verified_at is None:
                recipient.verified_at = timezone.now()
                recipient.save(update_fields=["verified_at"])
                record_audit(
                    AuditAction.RUN_EMAIL_RECIPIENT_VERIFY,
                    actor=None,
                    organization=recipient.organization,
                    target=recipient,
                )
    return JsonResponse({
        "organization_name": recipient.organization.name,
        "email": recipient.email,
        "verified": recipient.verified_at is not None,
    })


@never_cache
@require_http_methods(["GET"])
@handle_notification_errors
def template_metadata(request: HttpRequest) -> JsonResponse:
    membership = get_request_membership(request)
    if isinstance(membership, JsonResponse):
        return membership
    build_organization_access(membership, channel=AccessChannel.SESSION)
    return JsonResponse(get_template_metadata())
