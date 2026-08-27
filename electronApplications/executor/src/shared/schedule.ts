// FileName: schedule.ts

import type { Dict_RunOptions } from "./runOptions";

export type Str_RunConflictPolicy = "skip" | "wait" | "concurrent";

export interface Dict_ListItem_Schedule {
  name: string;
  project_name: string;
  project_version: string;
  cron: string;
  enable: boolean;
  period_start_ms: number;
  period_end_ms: number;
  run_conflict_policy: Str_RunConflictPolicy;
}

export interface Dict_Detail_Schedule extends Dict_ListItem_Schedule, Dict_RunOptions {
  id: number;
  project_id: number;
  created_at_ms: number;
  updated_at_ms: number;
}

export type Dict_ScheduleCreate = Omit<
  Dict_Detail_Schedule,
  "id" | "created_at_ms" | "updated_at_ms" | "project_name" | "project_version"
>;

export type Dict_ScheduleUpdate = Dict_ScheduleCreate & {
  id: number;
};
