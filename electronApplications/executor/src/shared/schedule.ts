// FileName: schedule.ts

import type { DictRunOptions } from "./runOptions";

export type TypeRunConflictPolicy = "skip" | "wait" | "concurrent";

export interface DictScheduleListItem {
  name: string;
  project_name: string;
  project_version: string;
  cron: string;
  enable: boolean;
  period_start_ms: number;
  period_end_ms: number;
  run_conflict_policy: TypeRunConflictPolicy;
}

export interface DictScheduleDetail extends DictScheduleListItem, DictRunOptions {
  id: number;
  project_id: number;
  created_at_ms: number;
  updated_at_ms: number;
}

export type DictScheduleCreate = Omit<
  DictScheduleDetail,
  "id" | "created_at_ms" | "updated_at_ms" | "project_name" | "project_version"
>;

export type DictScheduleUpdate = DictScheduleCreate & {
  id: number;
};
