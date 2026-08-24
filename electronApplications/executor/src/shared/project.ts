// FileName: project.ts

import type { DictPythonEnvironmentSelection, DictRunOptions } from "./runOptions";

export interface DictProjectDetail extends DictRunOptions, DictPythonEnvironmentSelection {
  id: number;
  name: string;
  version: string;
  description: string;
  version_summary: string;
  created_at_ms: number;
  updated_at_ms: number;
}

export type DictProjectCreate = Omit<
  DictProjectDetail,
  "id" | "created_at_ms" | "updated_at_ms"
>;

export interface DictProjectSettingsUpdate
  extends DictRunOptions, DictPythonEnvironmentSelection {
  id: number;
}

export type DictProjectPackageImportResult =
  | { status: "canceled" }
  | {
      status: "projectPackageImported";
      name: string;
      version: string;
    };
