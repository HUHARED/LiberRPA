// FileName: types.ts

import type { ScheduleDetails } from "../../../shared/schedule";

export type ScheduleEditDraft = Omit<
  ScheduleDetails,
  "period_start_ms" | "period_end_ms" | "project_id"
> & {
  project_id: number | undefined;
  period_start: string;
  period_end: string;
};

export type ScheduleCreateDraft = Omit<
  ScheduleEditDraft,
  | "id"
  | "project_id"
  | "project_name"
  | "project_version"
  | "created_at_ms"
  | "updated_at_ms"
> & {
  project_id: number | undefined;
  project_name: string | undefined;
  project_version: string | undefined;
};

export type ScheduleFormDraft = ScheduleEditDraft | ScheduleCreateDraft;
