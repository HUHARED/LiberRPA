// FileName: types.ts

import type { Dict_Detail_Schedule } from "../../../shared/schedule";

export type Dict_Detail_ScheduleForm_All = Omit<
  Dict_Detail_Schedule,
  "period_start_ms" | "period_end_ms" | "project_id"
> & {
  project_id: number | undefined;
  period_start: string;
  period_end: string;
};

export type Dict_Detail_NewScheduleForm = Omit<
  Dict_Detail_ScheduleForm_All,
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

export type Dict_Detail_ScheduleForm =
  | Dict_Detail_ScheduleForm_All
  | Dict_Detail_NewScheduleForm;
