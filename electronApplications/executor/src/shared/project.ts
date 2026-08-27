// FileName: project.ts

import type { Dict_PythonEnvironmentSelection, Dict_RunOptions } from "./runOptions";

export interface Dict_ProjectDetail
  extends Dict_RunOptions, Dict_PythonEnvironmentSelection {
  id: number;
  name: string;
  version: string;
  description: string;
  version_summary: string;

  created_at_ms: number;
  updated_at_ms: number;
}

export type Dict_ProjectCreate = Omit<
  Dict_ProjectDetail,
  "id" | "created_at_ms" | "updated_at_ms"
>;

export interface Dict_ProjectSettingsUpdate
  extends Dict_RunOptions, Dict_PythonEnvironmentSelection {
  id: number;
}

export type Dict_ProjectPackage_ImportResult =
  | { status: "canceled" }
  | {
      status: "projectPackageImported";
      name: string;
      version: string;
    };
