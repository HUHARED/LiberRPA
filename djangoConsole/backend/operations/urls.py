# FileName: urls.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from django.urls import path

from .audit_views import (
    list_organization_audit,
    get_organization_audit_filters,
    get_organization_audit_details,
)

urlpatterns = [
    path("organization/audit/", list_organization_audit, name="organization-audit"),
    path(
        "organization/audit/filters/",
        get_organization_audit_filters,
        name="organization-audit-filters",
    ),
    path(
        "organization/audit/<uuid:auditId>/",
        get_organization_audit_details,
        name="organization-audit-details",
    ),
]
