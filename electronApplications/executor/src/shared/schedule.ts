// FileName: schedule.ts

import type {
  DictColumns_RunOptions_ExecutionEnvironment,
  DictColumns_RunOptions_NeedConvert_DB,
  DictColumns_RunOptions_NeedConvert_TS,
  DictColumns_RunOptions_TimeoutAndLog,
  TypeColumns_RunOptions_NeedConvert,
} from "./runOptions";

interface DictColumns_Base_DB {
  id: number;
  created_at_ms: number;
  updated_at_ms: number;
}

type TypeColumns_ModifyTime = "created_at_ms" | "updated_at_ms";

export interface DictColumns_Schedule_ListItem_DB {
  name: string;
  project_source: "local" | "console";
  project_name: string;
  project_version: string;
  cron: string;
  enable: 0 | 1;

  // These values are not displayed in the Schedule list, but the Scheduler engine needs them.
  period_start_ms: number;
  period_end_ms: number;
  when_others_running: "cancel" | "wait" | "run";
}

export type DictColumns_Schedule_ListItem = Omit<
  DictColumns_Schedule_ListItem_DB,
  "enable"
> & {
  enable: boolean;
};

export interface DictColumns_Schedule_Detail_DB
  extends
    DictColumns_Base_DB,
    DictColumns_Schedule_ListItem_DB,
    DictColumns_RunOptions_NeedConvert_DB,
    DictColumns_RunOptions_TimeoutAndLog,
    DictColumns_RunOptions_ExecutionEnvironment {
  project_id: number;
}

export type DictColumns_Schedule_Detail = Omit<
  DictColumns_Schedule_Detail_DB,
  TypeColumns_RunOptions_NeedConvert | "enable" | "period_start_ms" | "period_end_ms"
> &
  DictColumns_RunOptions_NeedConvert_TS & {
    enable: boolean;
    period_start: string;
    period_end: string;
  };

export type DictColumns_Schedule_Detail_ToUpdate = Omit<
  DictColumns_Schedule_Detail_DB,
  TypeColumns_ModifyTime | "project_name" | "project_version" | "python_environment_name"
>;

export type DictColumns_Schedule_Detail_ToInsert = Omit<
  DictColumns_Schedule_Detail_DB,
  | "id"
  | TypeColumns_ModifyTime
  | "project_name"
  | "project_version"
  | "python_environment_name"
>;

export type DictColumns_Schedule_Detail_BeforeInsert = Omit<
  DictColumns_Schedule_Detail,
  | "id"
  | TypeColumns_ModifyTime
  | "project_id"
  | "project_name"
  | "project_version"
  | "python_environment_name"
> & {
  project_id: number | undefined;
  project_name: string | undefined;
  project_version: string | undefined;
};
