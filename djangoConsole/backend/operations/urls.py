# FileName: urls.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.urls import path

from .audit_views import (
    list_audit,
    get_audit_filters,
    get_audit_details,
)
from .models import AuditScope
from .service_settings_views import get_or_update_service_settings
from .instance_views import get_instance_summary, get_instance_status
from .email_views import list_email_issues, get_email_issue_filters
from .organization_views import (
    list_platform_organizations,
    get_platform_organization,
    update_organization_service,
    get_or_update_organization_limits,
)

urlpatterns = [
    path(
        "platform/service-settings/",
        get_or_update_service_settings,
        name="platform-service-settings",
    ),
    path("platform/email-issues/", list_email_issues, name="platform-email-issues"),
    path(
        "platform/email-issues/filters/",
        get_email_issue_filters,
        name="platform-email-issue-filters",
    ),
    path(
        "platform/instance-status/summary/",
        get_instance_summary,
        name="platform-instance-summary",
    ),
    path(
        "platform/instance-status/",
        get_instance_status,
        name="platform-instance-status",
    ),
    path(
        "platform/organizations/",
        list_platform_organizations,
        name="platform-organizations",
    ),
    path(
        "platform/organizations/<uuid:organizationId>/",
        get_platform_organization,
        name="platform-organization-details",
    ),
    path(
        "platform/organizations/<uuid:organizationId>/service/",
        update_organization_service,
        name="platform-organization-service",
    ),
    path(
        "platform/organizations/<uuid:organizationId>/limits/",
        get_or_update_organization_limits,
        name="platform-organization-limits",
    ),
    path(
        "platform/audit/",
        list_audit,
        {"scope": AuditScope.PLATFORM},
        name="platform-audit",
    ),
    path(
        "platform/audit/filters/",
        get_audit_filters,
        {"scope": AuditScope.PLATFORM},
        name="platform-audit-filters",
    ),
    path(
        "platform/audit/<uuid:auditId>/",
        get_audit_details,
        {"scope": AuditScope.PLATFORM},
        name="platform-audit-details",
    ),
    path("organization/audit/", list_audit, name="organization-audit"),
    path(
        "organization/audit/filters/",
        get_audit_filters,
        name="organization-audit-filters",
    ),
    path(
        "organization/audit/<uuid:auditId>/",
        get_audit_details,
        name="organization-audit-details",
    ),
]
