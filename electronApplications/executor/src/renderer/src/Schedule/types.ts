import type { DictScheduleDetail } from "../../../shared/schedule";

export type DictScheduleFormDetail = Omit<
  DictScheduleDetail,
  "period_start_ms" | "period_end_ms" | "project_id"
> & {
  project_id: number | undefined;
  period_start: string;
  period_end: string;
};

export type DictNewScheduleFormDetail = Omit<
  DictScheduleFormDetail,
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

export type TypeScheduleFormDetail = DictScheduleFormDetail | DictNewScheduleFormDetail;
