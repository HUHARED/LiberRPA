// FileName: schedule.ts

import type { RunConflictPolicy, RunSettings } from "./runSettings";

export interface ScheduleListItem {
  id: number;
  name: string;
  project_name: string;
  project_version: string;
  cron: string;
  enabled: boolean;
  period_start_ms: number;
  period_end_ms: number;
  run_conflict_policy: RunConflictPolicy;
}

export interface ScheduleDetails extends ScheduleListItem, RunSettings {
  project_id: number;
  python_environment_name: string;
  created_at_ms: number;
  updated_at_ms: number;
}

export type ScheduleCreateData = Omit<
  ScheduleDetails,
  | "id"
  | "created_at_ms"
  | "updated_at_ms"
  | "project_name"
  | "project_version"
  | "python_environment_name"
>;

export type ScheduleUpdateData = ScheduleCreateData & {
  id: number;
};
