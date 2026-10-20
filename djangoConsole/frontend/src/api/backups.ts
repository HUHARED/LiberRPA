// FileName: backups.ts

import { requestApi } from "./client";
import {
  isRecord,
  isDateString,
  isNullableDateString,
  isNonnegativeInteger,
  isNullableString,
  rejectInvalidResponse,
} from "./responses";

import {
  ARR_INSTANCE_HEALTH_STATUS,
  ARR_BACKUP_STAGE,
  ARR_BACKUP_SOURCE,
  ARR_BACKUP_STATUS,
  type BackupRecordResponse,
  type BackupStatusResponse,
} from "./generated/browserApi";

function parseBackupStatusResponse(payload: unknown): BackupStatusResponse {
  function parseRecord(value: unknown): BackupRecordResponse | null {
    if (value === null) return null;
    if (!isRecord(value)) return rejectInvalidResponse();
    const source = ARR_BACKUP_SOURCE.find((entry) => entry === value.source);
    const status = ARR_BACKUP_STATUS.find((entry) => entry === value.status);
    const stage =
      value.stage === null ? null : ARR_BACKUP_STAGE.find((entry) => entry === value.stage);
    if (
      typeof value.id !== "string" ||
      !value.id ||
      source === undefined ||
      status === undefined ||
      stage === undefined ||
      !isDateString(value.created_at) ||
      !isNullableDateString(value.started_at) ||
      !isNullableDateString(value.ended_at) ||
      !isNullableDateString(value.data_as_of) ||
      (value.size_bytes !== null && !isNonnegativeInteger(value.size_bytes)) ||
      typeof value.details !== "string" ||
      typeof value.cleanup_error !== "string"
    )
      return rejectInvalidResponse();
    return {
      id: value.id,
      source,
      status,
      stage,
      created_at: value.created_at,
      started_at: value.started_at,
      ended_at: value.ended_at,
      data_as_of: value.data_as_of,
      size_bytes: value.size_bytes,
      details: value.details,
      cleanup_error: value.cleanup_error,
    };
  }

  if (!isRecord(payload)) return rejectInvalidResponse();
  const healthStatus = ARR_INSTANCE_HEALTH_STATUS.find(
    (value) => value === payload.health_status,
  );
  if (
    typeof payload.configured !== "boolean" ||
    !isNullableString(payload.location) ||
    !isNullableString(payload.daily_time) ||
    typeof payload.time_zone !== "string" ||
    !payload.time_zone ||
    !isNonnegativeInteger(payload.retention_count) ||
    healthStatus === undefined ||
    !isNullableDateString(payload.checked_at) ||
    typeof payload.health_message !== "string" ||
    typeof payload.can_start !== "boolean" ||
    typeof payload.blocked_reason !== "string" ||
    !isDateString(payload.updated_at)
  )
    return rejectInvalidResponse();

  return {
    configured: payload.configured,
    location: payload.location,
    daily_time: payload.daily_time,
    time_zone: payload.time_zone,
    retention_count: payload.retention_count,
    current: parseRecord(payload.current),
    latest_result: parseRecord(payload.latest_result),
    last_success: parseRecord(payload.last_success),
    health_status: healthStatus,
    checked_at: payload.checked_at,
    health_message: payload.health_message,
    can_start: payload.can_start,
    blocked_reason: payload.blocked_reason,
    updated_at: payload.updated_at,
  };
}

export async function getBackups(): Promise<BackupStatusResponse> {
  return parseBackupStatusResponse(await requestApi("/platform/backups/"));
}

export async function requestBackup(): Promise<BackupStatusResponse> {
  return parseBackupStatusResponse(
    await requestApi("/platform/backups/", { method: "POST", body: {} }),
  );
}
