// FileName: project.ts

import type { DictPythonEnvironmentSelection, DictRunOptions } from "./runOptions";

export type TypeProjectSource = "local" | "console";

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

export type DictProjectUpdate = Omit<DictProjectDetail, "created_at_ms" | "updated_at_ms">;

export type DictProjectPackageImportResult =
  | { status: "canceled" }
  | {
      status: "projectPackageImported";
      name: string;
      version: string;
      packageFilePath: string;
      installedFolderPath: string;
    };
