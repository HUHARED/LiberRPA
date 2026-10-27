# FileName: generate_browser_contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

import argparse
import json
import subprocess
import sys
from pathlib import Path

from pydantic import BaseModel
from pydantic.json_schema import JsonSchemaMode, JsonSchemaValue, models_json_schema

_PATH_CONSOLE = Path(__file__).resolve().parents[1]
# The standalone command imports contract modules without loading Django settings.
sys.path.insert(0, str(_PATH_CONSOLE / "backend"))

from console_project import contracts as commonContracts
from console_project.constants import INT_LIST_PAGE_SIZE
from accounts import contracts as accountContracts
from organizations import contracts as organizationContracts
from assets import contracts as assetContracts
from data_queues import contracts as queueContracts
from shared_files import contracts as fileContracts
from executors import contracts as executorContracts
from operations import contracts as operationContracts
from operations import audit_contracts as auditContracts
from packages import contracts as packageContracts
from schedules import contracts as scheduleContracts
from runs import contracts as runContracts
from notifications import contracts as notificationContracts

# NOTE: Register browser contracts explicitly; keep each group in its source declaration order.
_BROWSER_CONTRACTS: tuple[tuple[type[BaseModel], JsonSchemaMode], ...] = (
    # Shared responses.
    (commonContracts.MessageResponse, "serialization"),
    # Account sessions, profile, email and API keys.
    (accountContracts.BrowserEventResponse, "serialization"),
    (accountContracts.LoginRequest, "validation"),
    (accountContracts.PlatformLoginRequest, "validation"),
    (accountContracts.SessionResponse, "serialization"),
    (accountContracts.CsrfResponse, "serialization"),
    (accountContracts.ProfileUpdateRequest, "validation"),
    (accountContracts.PlatformTimeZoneRequest, "validation"),
    (accountContracts.ProfileWriteResponse, "serialization"),
    (accountContracts.PasswordChangeRequest, "validation"),
    (accountContracts.SessionRevocationRequest, "validation"),
    (accountContracts.EmailChangeEmailRequest, "validation"),
    (accountContracts.EmailChangeTokenRequest, "validation"),
    (accountContracts.EmailChangeInfoResponse, "serialization"),
    (accountContracts.AccountDeletionRequest, "validation"),
    (accountContracts.AccountDeletionPreviewResponse, "serialization"),
    (accountContracts.ApiKeyCreateRequest, "validation"),
    (accountContracts.ApiKeyNotesRequest, "validation"),
    (accountContracts.ApiKeyWriteResponse, "serialization"),
    (accountContracts.ApiKeyCreationResponse, "serialization"),
    (accountContracts.ApiKeyListResponse, "serialization"),
    # Organization access, departments, members and invitations.
    (organizationContracts.AccountAccessResponse, "serialization"),
    (organizationContracts.OrganizationSettingsRequest, "validation"),
    (organizationContracts.OrganizationRetentionRequest, "validation"),
    (organizationContracts.OrganizationSettingsResponse, "serialization"),
    (organizationContracts.OrganizationDeletionRequest, "validation"),
    (organizationContracts.OrganizationDeletionResponse, "serialization"),
    (organizationContracts.DepartmentUpdateRequest, "validation"),
    (organizationContracts.DepartmentCreationRequest, "validation"),
    (organizationContracts.DepartmentDeletionRequest, "validation"),
    (organizationContracts.DepartmentWriteResponse, "serialization"),
    (organizationContracts.DepartmentListResponse, "serialization"),
    (organizationContracts.DepartmentDetailsResponse, "serialization"),
    (organizationContracts.DepartmentDeletionPreviewResponse, "serialization"),
    (organizationContracts.DepartmentDeletionResponse, "serialization"),
    (organizationContracts.MemberListResponse, "serialization"),
    (organizationContracts.MemberDetailsResponse, "serialization"),
    (organizationContracts.MembershipUpdateRequest, "validation"),
    (organizationContracts.MembershipWriteResponse, "serialization"),
    (organizationContracts.InvitationCreateRequest, "validation"),
    (organizationContracts.InvitationTokenRequest, "validation"),
    (organizationContracts.InvitationCompletionRequest, "validation"),
    (organizationContracts.InvitationRegistrationResponse, "serialization"),
    (organizationContracts.InvitationDetailsResponse, "serialization"),
    (organizationContracts.InvitationListResponse, "serialization"),
    # Assets.
    (assetContracts.AssetDetailsRequest, "validation"),
    (assetContracts.AssetCreationRequest, "validation"),
    (assetContracts.AssetUpdateRequest, "validation"),
    (assetContracts.AssetDeletionRequest, "validation"),
    (assetContracts.AssetListResponse, "serialization"),
    (assetContracts.AssetDetailsResponse, "serialization"),
    (assetContracts.AssetDeletionPreviewResponse, "serialization"),
    # Data queues.
    (queueContracts.QueueDetailsRequest, "validation"),
    (queueContracts.QueueCreationRequest, "validation"),
    (queueContracts.QueueUploadRequest, "validation"),
    (queueContracts.QueueResetRequest, "validation"),
    (queueContracts.QueueDeleteItemsRequest, "validation"),
    (queueContracts.QueueDetailsResponse, "serialization"),
    (queueContracts.QueueListResponse, "serialization"),
    (queueContracts.QueueItemDetailsResponse, "serialization"),
    (queueContracts.QueueItemsResponse, "serialization"),
    (queueContracts.QueueMutationResponse, "serialization"),
    # Shared files.
    (fileContracts.FileListRequest, "validation"),
    (fileContracts.FilePathRequest, "validation"),
    (fileContracts.FileUploadRequest, "validation"),
    (fileContracts.FileDeleteRequest, "validation"),
    (fileContracts.FileInfoResponse, "serialization"),
    (fileContracts.FileUsageResponse, "serialization"),
    (fileContracts.FileListResponse, "serialization"),
    (fileContracts.FileUploadResponse, "serialization"),
    (fileContracts.FileDeleteResponse, "serialization"),
    (fileContracts.FileDownloadResponse, "serialization"),
    # Executors and executor groups.
    (executorContracts.ExecutorUpdateRequest, "validation"),
    (executorContracts.ExecutorCreationRequest, "validation"),
    (executorContracts.ExecutorDeletionRequest, "validation"),
    (executorContracts.ExecutorDispatchRequest, "validation"),
    (executorContracts.ExecutorUnassociateRequest, "validation"),
    (executorContracts.ExecutorUpdateResponse, "serialization"),
    (executorContracts.ExecutorListResponse, "serialization"),
    (executorContracts.ExecutorDetailsResponse, "serialization"),
    (executorContracts.ExecutorGroupUpdateRequest, "validation"),
    (executorContracts.ExecutorGroupCreationRequest, "validation"),
    (executorContracts.ExecutorGroupDeletionRequest, "validation"),
    (executorContracts.ExecutorGroupListResponse, "serialization"),
    (executorContracts.ExecutorGroupDetailsResponse, "serialization"),
    (executorContracts.ExecutorGroupWriteResponse, "serialization"),
    (executorContracts.RunTargetOptionsResponse, "serialization"),
    # Package settings, imports and preparation.
    (packageContracts.PackageUploadRequest, "validation"),
    (packageContracts.PackageSettingsRequest, "validation"),
    (packageContracts.PackageListEntryResponse, "serialization"),
    (packageContracts.PackageDetailsResponse, "serialization"),
    (packageContracts.PackageProjectGroupListResponse, "serialization"),
    (packageContracts.ProjectPackageListResponse, "serialization"),
    (packageContracts.PackageOptionsResponse, "serialization"),
    (packageContracts.PackageUploadResponse, "serialization"),
    (packageContracts.PackagePreparationCancellationResponse, "serialization"),
    (packageContracts.PackageDownloadResponse, "serialization"),
    # Schedule configuration and previews.
    (scheduleContracts.ScheduleTimeRequest, "validation"),
    (scheduleContracts.ScheduleSaveRequest, "validation"),
    (scheduleContracts.ScheduleEnabledRequest, "validation"),
    (scheduleContracts.ScheduleListResponse, "serialization"),
    (scheduleContracts.ScheduleDetailsResponse, "serialization"),
    (scheduleContracts.SchedulePreviewResponse, "serialization"),
    # Jobs, actual runs, logs and original files.
    (runContracts.JobCreationRequest, "validation"),
    (runContracts.JobControlRequest, "validation"),
    (runContracts.ClearLogsRequest, "validation"),
    (runContracts.RunFileRequest, "validation"),
    (runContracts.JobDetailsResponse, "serialization"),
    (runContracts.JobListResponse, "serialization"),
    (runContracts.JobCreationResponse, "serialization"),
    (runContracts.RunDetailsResponse, "serialization"),
    (runContracts.RunListResponse, "serialization"),
    (runContracts.CurrentRunListResponse, "serialization"),
    (runContracts.RunStatisticsResponse, "serialization"),
    (runContracts.RunSelectionResponse, "serialization"),
    (runContracts.RunRerunResponse, "serialization"),
    (runContracts.RunLogListResponse, "serialization"),
    (runContracts.RunLogClearResponse, "serialization"),
    (runContracts.RunDownloadResponse, "serialization"),
    (runContracts.RunDepartmentListResponse, "serialization"),
    # Personal notifications.
    (notificationContracts.NotificationListResponse, "serialization"),
    (notificationContracts.NotificationDetailsResponse, "serialization"),
    (notificationContracts.NotificationReadResponse, "serialization"),
    # Run email recipients.
    (notificationContracts.RecipientCreationRequest, "validation"),
    (notificationContracts.RecipientNotesRequest, "validation"),
    (notificationContracts.RecipientTokenRequest, "validation"),
    (notificationContracts.RunEmailRecipientListResponse, "serialization"),
    (notificationContracts.RunEmailVerificationResponse, "serialization"),
    # Organization quota management.
    (operationContracts.PlatformOrganizationFilters, "validation"),
    (operationContracts.PlatformOrganizationDetailsResponse, "serialization"),
    (operationContracts.OrganizationServiceRequest, "validation"),
    (operationContracts.PlatformOrganizationListResponse, "serialization"),
    (operationContracts.OrganizationLimitsRequest, "validation"),
    (operationContracts.OrganizationLimitsResponse, "serialization"),
    # Platform service settings.
    (operationContracts.ServiceSettingsRequest, "validation"),
    (operationContracts.ServiceSettingsResponse, "serialization"),
    # Platform email diagnostics.
    (operationContracts.EmailIssueListResponse, "serialization"),
    (operationContracts.EmailIssueFiltersResponse, "serialization"),
    # Audit history.
    (auditContracts.AuditListResponse, "serialization"),
    (auditContracts.PlatformAuditListResponse, "serialization"),
    (auditContracts.AuditFilterOptionsResponse, "serialization"),
    (auditContracts.PlatformAuditFilterOptionsResponse, "serialization"),
    (auditContracts.AuditDetailsResponse, "serialization"),
)


def _build_browser_contract_schema() -> JsonSchemaValue:
    """Export only public browser payloads, without settings, secrets or a database."""
    dictReference, dictSchema = models_json_schema(_BROWSER_CONTRACTS)
    dictSchema.update({
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "BrowserApiContracts",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            contractModel.__name__: dictReference[(contractModel, strMode)]
            for contractModel, strMode in _BROWSER_CONTRACTS
        },
        "required": [contractModel.__name__ for contractModel, _ in _BROWSER_CONTRACTS],
    })
    return dictSchema


def main() -> int:
    argumentParser = argparse.ArgumentParser(
        description="Generate browser API TypeScript types from backend contracts, or check them without changing the file."
    )
    argumentParser.add_argument("--check", action="store_true")
    argumentParser.add_argument(
        "--node",
        default="node",
        help="Node.js executable path (default: node from PATH).",
    )
    arguments = argumentParser.parse_args()
    boolCheck = bool(arguments.check)
    strNodePath: str = arguments.node
    pathOutput = _PATH_CONSOLE / "frontend/src/api/generated/browserApi.ts"
    # Keep the schema in memory and let the existing converter handle TypeScript syntax.
    try:
        completedProcess = subprocess.run(
            [
                strNodePath,
                str(_PATH_CONSOLE / "frontend/scripts/generateApiTypes.mjs"),
            ],
            cwd=_PATH_CONSOLE,
            input=json.dumps(
                {
                    "schema": _build_browser_contract_schema(),
                    "list_page_size": INT_LIST_PAGE_SIZE,
                    "audit_actions": auditContracts.AuditAction.choices,
                    "max_organization_service_reason_length": operationContracts.INT_ORGANIZATION_SERVICE_REASON_MAX_LENGTH,
                    "max_run_statistics_days": runContracts.INT_MAX_RUN_STATISTICS_DAYS,
                },
                sort_keys=True,
            ),
            stdout=subprocess.PIPE,
            encoding="utf-8",
            check=False,
        )
    except FileNotFoundError:
        print(
            "Node.js was not found. Add it to PATH or pass --node with its executable path.",
            file=sys.stderr,
        )
        return 1
    if completedProcess.returncode != 0:
        return 1
    strExpected = completedProcess.stdout
    if boolCheck:
        if (
            not pathOutput.is_file()
            or pathOutput.read_text(encoding="utf-8") != strExpected
        ):
            print(
                "Browser API types are out of date. Run this command again without --check.",
                file=sys.stderr,
            )
            return 1
    else:
        pathOutput.parent.mkdir(parents=True, exist_ok=True)
        pathOutput.write_text(strExpected, encoding="utf-8", newline="\n")
    if boolCheck:
        print("Browser API TypeScript types match backend contracts.")
    else:
        print("Browser API TypeScript types generated from backend contracts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
