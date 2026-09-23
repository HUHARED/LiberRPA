# FileName: creation.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import uuid
from dataclasses import dataclass
from typing import cast

from django.core.exceptions import ValidationError
from django.db import transaction
from django.views.decorators.debug import sensitive_variables

from accounts.models import User, UserManager
from operations.policies import require_organization_creation_allowed

from .department_services import create_general_department
from .models import Department, Membership, Organization


@dataclass(frozen=True)
class OrganizationCreationResult:
    """Records created together for an authorized organization registration."""

    user: User
    organization: Organization
    membership: Membership
    generalDepartment: Department


@sensitive_variables()
@transaction.atomic
def create_organization_records(
    *,
    verifiedEmail: str,
    password: str,
    organizationName: str,
    username: str = "",
) -> OrganizationCreationResult:
    """Create the records for an organization registration already authorized by the caller.

    The registration entry point must verify and lock the email proof, then consume it in the same outer transaction.
    verifiedEmail must come from that proof, never from an independently editable form field.
    This internal creation step does not verify email ownership or open a login session.
    """
    require_organization_creation_allowed()
    # UserManager supports internal accounts without passwords, but registration requires one.
    if password is None:
        raise ValidationError({"password": "A password is required."})

    organization = Organization(name=organizationName.strip())
    organization.full_clean(validate_unique=False, validate_constraints=False)

    # Display names are not unique, so a generated name needs no availability query.
    displayName = (
        username
        if username and not username.isspace()
        else f"User {uuid.uuid4().hex[:8]}"
    )
    userManager = cast(UserManager, User.objects)
    # Copy the initial time zone once; later profile edits remain independent.
    user = userManager.create_user(
        verifiedEmail,
        password,
        username=displayName,
        timeZone=organization.default_time_zone,
    )
    organization.save(force_insert=True)
    membership = Membership(user=user, organization=organization, is_org_admin=True)
    membership.save(force_insert=True)

    # The new organization is private to this transaction until it commits.
    # General follows the same validation and quota rules as any other department.
    generalDepartment = create_general_department(organization)
    return OrganizationCreationResult(
        user=user,
        organization=organization,
        membership=membership,
        generalDepartment=generalDepartment,
    )
