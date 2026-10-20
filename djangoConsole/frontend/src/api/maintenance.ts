// FileName: maintenance.ts

import { requestApi } from "./client";
import {
  isRecord,
  isDateString,
  isNullableDateString,
  isNonnegativeInteger,
  rejectInvalidResponse,
} from "./responses";

import {
  ARR_SERVICE_STATE,
  type MaintenanceRequest,
  type MaintenanceResponse,
  type RunActivityResponse,
} from "./generated/browserApi";

function parseMaintenanceResponse(payload: unknown): MaintenanceResponse {
  if (!isRecord(payload)) return rejectInvalidResponse();
  const state = ARR_SERVICE_STATE.find((value) => value === payload.state);
  if (
    state === undefined ||
    !isNullableDateString(payload.entered_at) ||
    !isNonnegativeInteger(payload.active_jobs) ||
    !isNonnegativeInteger(payload.running_runs) ||
    !isNonnegativeInteger(payload.jobs_needing_review) ||
    typeof payload.can_resume !== "boolean" ||
    typeof payload.resume_block_reason !== "string" ||
    !isDateString(payload.updated_at)
  )
    return rejectInvalidResponse();

  return {
    state,
    entered_at: payload.entered_at,
    active_jobs: payload.active_jobs,
    running_runs: payload.running_runs,
    jobs_needing_review: payload.jobs_needing_review,
    can_resume: payload.can_resume,
    resume_block_reason: payload.resume_block_reason,
    updated_at: payload.updated_at,
  };
}

export async function getMaintenance(): Promise<MaintenanceResponse> {
  return parseMaintenanceResponse(await requestApi("/platform/maintenance/"));
}

export async function updateMaintenance(
  request: MaintenanceRequest,
): Promise<MaintenanceResponse> {
  return parseMaintenanceResponse(
    await requestApi("/platform/maintenance/", { method: "POST", body: request }),
  );
}

export async function getRunActivity(): Promise<RunActivityResponse> {
  const payload = await requestApi("/platform/maintenance/run-activity/");
  if (
    !isRecord(payload) ||
    typeof payload.time_zone !== "string" ||
    !payload.time_zone ||
    !isDateString(payload.start_date) ||
    !isDateString(payload.end_date) ||
    !isDateString(payload.updated_at) ||
    !isNonnegativeInteger(payload.incomplete_run_count) ||
    !Array.isArray(payload.hours) ||
    payload.hours.length !== 24 ||
    !payload.hours.every(
      (entry: unknown, intHour): entry is RunActivityResponse["hours"][number] =>
        isRecord(entry) && entry.hour === intHour && isNonnegativeInteger(entry.run_count),
    )
  )
    return rejectInvalidResponse();

  return {
    time_zone: payload.time_zone,
    start_date: payload.start_date,
    end_date: payload.end_date,
    updated_at: payload.updated_at,
    hours: payload.hours,
    incomplete_run_count: payload.incomplete_run_count,
  };
}
