# FileName: contracts.py
__author__ = "Jiyan Hu"
__email__ = "mailwork.hu@gmail.com"
__license__ = "GNU Affero General Public License v3.0 or later"
__copyright__ = f"Copyright (C) 2025 {__author__}"

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from accounts.contracts import UserResponse
from console_project.contracts import JsonRequest, JsonResponsePayload, PaginationResponse
from packages.contracts import PackagePreparationState


class ExecutorAssociationStatus(StrEnum):
    UNASSOCIATED = "unassociated"
    ONLINE = "online"
    OFFLINE = "offline"


class ExecutorUpdateRequest(JsonRequest):
    name: str
    notes: str


class ExecutorCreationRequest(ExecutorUpdateRequest):
    department_id: Annotated[UUID, Field(strict=False)]
    notes: str = ""


class ExecutorDeletionRequest(JsonRequest):
    """The URL supplies the ID; the server checks current authorization and dependencies."""


class ExecutorDispatchRequest(JsonRequest):
    dispatch_enabled: bool


class ExecutorUnassociateRequest(JsonRequest):
    session_id: Annotated[UUID, Field(strict=False)]


class ExecutorDepartmentResponse(JsonResponsePayload):
    id: UUID
    name: str
    path: str


class ExecutorRecordResponse(JsonResponsePayload):
    id: UUID
    name: str
    department_id: UUID
    notes: str
    dispatch_enabled: bool
    created_at: datetime
    deleted_at: datetime | None


class ExecutorUpdateResponse(JsonResponsePayload):
    executor: ExecutorRecordResponse


class ExecutorListEntryResponse(ExecutorRecordResponse):
    department: ExecutorDepartmentResponse
    can_manage: bool
    association_status: ExecutorAssociationStatus
    session_id: UUID | None
    account: UserResponse | None
    computer_name: str | None
    client_version: str | None
    last_seen_at: datetime | None


class ExecutorListResponse(PaginationResponse):
    executors: list[ExecutorListEntryResponse]


class ExecutorGroupReferenceResponse(JsonResponsePayload):
    id: UUID
    name: str


class ExecutorScheduleReferenceResponse(JsonResponsePayload):
    id: UUID
    name: str
    enabled: bool


class ExecutorPreparationEntryResponse(JsonResponsePayload):
    id: UUID
    package_id: UUID
    project_name: str
    project_version: str
    python_environment_name: str
    state: PackagePreparationState
    reason: str
    updated_at: datetime
    from_previous_association: bool


class ExecutorPreparationPageResponse(PaginationResponse):
    items: list[ExecutorPreparationEntryResponse]


class ExecutorDetailsEntryResponse(ExecutorListEntryResponse):
    executor_groups: list[ExecutorGroupReferenceResponse]
    referencing_schedules: list[ExecutorScheduleReferenceResponse]
    other_active_run_count: int | None
    central_running_count: int | None
    local_waiting_count: int | None
    last_work_reported_at: datetime | None
    preparation: ExecutorPreparationPageResponse


class ExecutorDetailsResponse(JsonResponsePayload):
    executor: ExecutorDetailsEntryResponse


class ExecutorGroupUpdateRequest(JsonRequest):
    name: str
    notes: str
    executor_ids: list[Annotated[UUID, Field(strict=False)]]


class ExecutorGroupCreationRequest(ExecutorGroupUpdateRequest):
    department_id: Annotated[UUID, Field(strict=False)]
    notes: str = ""
    executor_ids: list[Annotated[UUID, Field(strict=False)]] = Field(default_factory=list)


class ExecutorGroupDeletionRequest(JsonRequest):
    """The URL supplies the group identity; request data cannot bypass reference checks."""


class ExecutorGroupRecordResponse(JsonResponsePayload):
    id: UUID
    name: str
    department_id: UUID
    notes: str
    created_at: datetime
    deleted_at: datetime | None


class ExecutorGroupListEntryResponse(ExecutorGroupRecordResponse):
    department: ExecutorDepartmentResponse
    can_manage: bool
    member_count: int
    online_count: int
    is_empty: bool


class ExecutorGroupListResponse(PaginationResponse):
    executor_groups: list[ExecutorGroupListEntryResponse]


class ExecutorGroupDetailsEntryResponse(ExecutorGroupListEntryResponse):
    members: list[ExecutorListEntryResponse]
    referencing_schedules: list[ExecutorScheduleReferenceResponse]


class ExecutorGroupDetailsResponse(JsonResponsePayload):
    executor_group: ExecutorGroupDetailsEntryResponse


class ExecutorGroupDeletionResponse(JsonResponsePayload):
    executor_group: ExecutorGroupRecordResponse


class ExecutorGroupWriteEntryResponse(ExecutorGroupRecordResponse):
    executor_ids: list[UUID]
    member_count: int
    is_empty: bool


class ExecutorGroupWarningResponse(JsonResponsePayload):
    code: Literal["empty_executor_group"]
    message: str


class ExecutorGroupWriteResponse(JsonResponsePayload):
    executor_group: ExecutorGroupWriteEntryResponse
    warnings: list[ExecutorGroupWarningResponse]
