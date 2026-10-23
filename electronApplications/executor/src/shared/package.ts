// FileName: package.ts

import type { RunSettings, PythonEnvironmentSelection } from "./runSettings";

// NOTE: Keep the project.flow limit aligned with Console and Project Manager.
export const INT_MAX_PROJECT_FLOW_BYTES = 8 * 1024 ** 2;

export interface PackageDetails extends RunSettings, PythonEnvironmentSelection {
  id: number;
  project_name: string;
  project_version: string;
  description: string;
  version_summary: string;

  created_at_ms: number;
  updated_at_ms: number;
}

export type PackageCreateData = Omit<
  PackageDetails,
  "id" | "created_at_ms" | "updated_at_ms"
>;

export interface PackageSettings extends RunSettings, PythonEnvironmentSelection {
  id: number;
}

export type PackageInstallResult =
  | { status: "canceled" }
  | {
      status: "packageInstalled";
      project_name: string;
      project_version: string;
    };
