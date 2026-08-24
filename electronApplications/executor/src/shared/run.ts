// FileName: run.ts

import type { TypeProjectSource } from "./project";

export type TypeRunHistoryStatus =
  | "running"
  | "completed"
  | "error"
  | "cancel"
  | "timeout"
  | "interrupted";

export interface DictRunHistoryItem {
  id: number;
  schedule_name: string | null;
  project_source: TypeProjectSource;
  project_name: string;
  project_version: string;
  python_environment_name: string;
  run_started_at_ms: number;
  run_ended_at_ms: number | null;
  status: TypeRunHistoryStatus;
}

export interface DictRunHistorySearch {
  schedule_name: string;
  project_source: TypeProjectSource | null;
  project_name: string;
  project_version: string;
  status: TypeRunHistoryStatus | null;
}

export interface DictRunHistoryOptions {
  page: number;
  itemsPerPage: number;
  sortBy: {
    key:
      | "schedule_name"
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
  rows: DictRunHistoryItem[];
  total: number;
}

export interface DictRunQueueListItem {
  schedule_name: string;
  project_source: TypeProjectSource;
  project_name: string;
  project_version: string;
  estimated_run_at_ms: number;
  waiting: boolean;
}
