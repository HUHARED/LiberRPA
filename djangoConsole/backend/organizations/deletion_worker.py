# FileName: deletion_worker.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from file_storage.services import clean_organization_storage
from shared_files.cleanup import prepare_organization_file_cleanup

from .cleanup import (
    OrganizationDeletionResult,
    start_next_organization_deletion,
    complete_organization_deletion,
)


def process_next_organization_deletion() -> OrganizationDeletionResult | None:
    """Process or resume one due deletion while the caller owns the worker session."""
    organizationId = start_next_organization_deletion()
    if organizationId is None:
        return None
    prepare_organization_file_cleanup(organizationId)
    if not clean_organization_storage(organizationId):
        return None
    return complete_organization_deletion(organizationId)
