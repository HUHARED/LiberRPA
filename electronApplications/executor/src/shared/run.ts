// FileName: run.ts

export type Str_RunHistory_Status =
  | "running"
  | "completed"
  | "error"
  | "cancel"
  | "timeout"
  | "interrupted";

export interface Dict_RunHistory_Item {
  id: number;
  schedule_name: string | null;
  project_name: string;
  project_version: string;
  python_environment_name: string;
  run_started_at_ms: number;
  run_ended_at_ms: number | null;
  status: Str_RunHistory_Status;
}

export interface Dict_RunHistory_Search {
  schedule_name: string;
  project_name: string;
  project_version: string;
  status: Str_RunHistory_Status | null;
}

export interface Dict_RunHistory_Options {
  page: number;
  itemsPerPage: number;
  sortBy: {
    key:
      | "schedule_name"
      | "project_name"
      | "project_version"
      | "python_environment_name"
      | "run_started_at_ms"
      | "run_ended_at_ms"
      | "status";
    order: "asc" | "desc";
  }[];
  // Vuetify also sends an unused groupBy value.
  search: Dict_RunHistory_Search;
}

export interface Dict_RunHistory_Page {
  rows: Dict_RunHistory_Item[];
  total: number;
}

export interface Dict_ListItem_RunQueue {
  queue_id: string;
  schedule_name: string;
  project_name: string;
  project_version: string;
  estimated_run_at_ms: number;
  waiting: boolean;
}
