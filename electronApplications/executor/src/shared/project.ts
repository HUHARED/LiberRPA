// FileName: project.ts

import type { RunOptions, PythonEnvironmentSelection } from "./runOptions";

export interface ProjectDetails extends RunOptions, PythonEnvironmentSelection {
  id: number;
  name: string;
  version: string;
  description: string;
  version_summary: string;

  created_at_ms: number;
  updated_at_ms: number;
}

export type ProjectCreateData = Omit<
  ProjectDetails,
  "id" | "created_at_ms" | "updated_at_ms"
>;

export interface ProjectSettingsUpdate extends RunOptions, PythonEnvironmentSelection {
  id: number;
}

export type ProjectPackageInstallResult =
  | { status: "canceled" }
  | {
      status: "projectPackageInstalled";
      name: string;
      version: string;
    };
