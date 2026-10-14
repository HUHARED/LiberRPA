// FileName: project.ts

import type { RunSettings, PythonEnvironmentSelection } from "./runSettings";

export interface ProjectDetails extends RunSettings, PythonEnvironmentSelection {
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

export interface ProjectSettingsUpdate extends RunSettings, PythonEnvironmentSelection {
  id: number;
}

export type ProjectPackageInstallResult =
  | { status: "canceled" }
  | {
      status: "projectPackageInstalled";
      name: string;
      version: string;
    };
