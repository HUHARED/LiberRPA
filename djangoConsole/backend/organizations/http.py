# FileName: http.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from typing import TypedDict, cast

from django.contrib.auth import HASH_SESSION_KEY
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, JsonResponse, QueryDict
from django.views.decorators.debug import sensitive_variables

from accounts.models import User
from accounts.session_revocation import lock_session_write_access
from console_project.http import build_authentication_required_response, parse_page_number

from .access import AccountAccessInfo
from .contracts import AccountAccessResponse
from .models import Membership
from .permissions import (
    AccessChannel,
    OrganizationAccessContext,
    get_current_membership,
    resolve_organization_access,
)


class DepartmentResourceListParameters(TypedDict):
    pageNumber: int
    departmentIds: tuple[uuid.UUID, ...]
    name: str


def get_request_membership(request: HttpRequest) -> Membership | JsonResponse:
    if not request.user.is_authenticated:
        return build_authentication_required_response()
    return get_current_membership(actorId=cast(User, request.user).id)


@sensitive_variables()
def lock_request_write_access(
    request: HttpRequest, membership: Membership
) -> OrganizationAccessContext:
    """Recheck the initiating Session and lock current access inside the view's transaction."""
    return lock_session_write_access(
        membership.user_id,
        membership.organization_id,
        AccessChannel.SESSION,
        request.session.get(HASH_SESSION_KEY, ""),
        request.session.get_expiry_date(),
        request.session.session_key,
    )


def get_request_access(
    request: HttpRequest, *, forUpdate: bool = False
) -> OrganizationAccessContext:
    membership = get_request_membership(request)
    if isinstance(membership, JsonResponse):
        raise PermissionDenied("Sign in to continue.")
    if forUpdate:
        return lock_request_write_access(request, membership)
    return resolve_organization_access(
        actorId=membership.user_id,
        organizationId=membership.organization_id,
        channel=AccessChannel.SESSION,
    )


def parse_department_resource_filters(
    query: QueryDict, *, extraFields: frozenset[str] = frozenset()
) -> DepartmentResourceListParameters:
    """Parse shared list filters without granting access to the selected departments."""
    if set(query) - {"page", "department_id", "name"} - extraFields:
        raise ValueError("Unknown list filters.")
    if len(query.getlist("name")) > 1:
        raise ValueError("Send one name filter.")
    strName = query.get("name", "").strip()
    listDepartmentValue = query.getlist("department_id")
    if len(strName) > 128 or len(listDepartmentValue) > 100:
        raise ValueError("Too many filter values or an overlong name.")
    return {
        "pageNumber": parse_page_number(query),
        "departmentIds": tuple(
            uuid.UUID(strDepartmentValue) for strDepartmentValue in listDepartmentValue
        ),
        "name": strName,
    }


def build_account_access_payload(
    accountAccessInfo: AccountAccessInfo,
) -> dict[str, object]:
    """Map internal access attributes to the shared HTTP response fields."""
    organizationInfo = accountAccessInfo.organization
    dictAccessPayload = {
        "organization": {
            "id": organizationInfo.id,
            "name": organizationInfo.name,
            "suspended_at": organizationInfo.suspendedAt,
            "deletion_requested_at": organizationInfo.deletionRequestedAt,
            "deletion_due_at": organizationInfo.deletionDueAt,
            "deletion_started_at": organizationInfo.deletionStartedAt,
        },
        "is_org_admin": accountAccessInfo.isOrgAdmin,
        "business_available": accountAccessInfo.businessAvailable,
        "departments": [
            {
                "id": departmentAccessInfo.id,
                "name": departmentAccessInfo.name,
                "path": departmentAccessInfo.path,
                "role": departmentAccessInfo.role,
            }
            for departmentAccessInfo in accountAccessInfo.departments
        ],
    }
    return AccountAccessResponse.model_validate(dictAccessPayload).model_dump(
        mode="python"
    )
