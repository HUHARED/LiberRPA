// FileName: run.ts

import type { DictColumns_Project_Detail } from "./project";

export type TypeRunHistoryStatus =
  | "running"
  | "completed"
  | "error"
  | "cancel"
  | "timeout"
  | "interrupted";

export type DictProjectRunDetail = Omit<
  DictColumns_Project_Detail,
  "created_at_ms" | "updated_at_ms" | "description" | "version_summary"
> & {
  schedule_name: string | null;
  project_source: "local" | "console";
};

// The SQLite schema keeps the historical scheduler_name column name.
// Runtime-only objects use schedule_name instead.
export interface DictColumns_RunHistory_ToInsert {
  scheduler_name: string | null;
  project_source: "local" | "console";
  project_id: number;
  project_name: string;
  project_version: string;
  python_environment_name: string;
  run_started_at_ms: number;
  status: "running";
  log_path: string;
}

export type DictColumns_RunHistory_ToUpdate =
  | {
      id: number;
      run_ended_at_ms: number;
      status: "completed" | "error" | "cancel" | "timeout";
    }
  | {
      id: number;
      run_ended_at_ms: null;
      status: "interrupted";
    };

export interface DictColumns_RunHistory_ListItem_DB {
  id: number;
  scheduler_name: string | null;
  project_source: "local" | "console";
  project_name: string;
  project_version: string;
  python_environment_name: string;
  run_started_at_ms: number;
  run_ended_at_ms: number | null;
  status: TypeRunHistoryStatus;
  log_path: string;
}

export interface DictRunHistorySearch {
  scheduler_name: string;
  project_source: "local" | "console" | null;
  project_name: string;
  project_version: string;
  status: TypeRunHistoryStatus | null;
}

export interface DictRunHistoryOptions {
  page: number;
  itemsPerPage: number;
  sortBy: {
    key:
      | "scheduler_name"
      | "project_source"
      | "project_name"
      | "project_version"
      | "python_environment_name"
      | "run_started_at_ms"
      | "run_ended_at_ms"
      | "status";
    order: "asc" | "desc";
  }[];
  // Vuetify also sends an unused groupBy value.
  search: DictRunHistorySearch;
}

export interface DictRunHistoryPage {
  rows: DictColumns_RunHistory_ListItem_DB[];
  total: number;
}

export interface DictRunQueueListItem {
  schedule_name: string;
  project_source: "local" | "console";
  project_name: string;
  project_version: string;
  estimated_run_at_ms: number;
  waiting: boolean;
}
