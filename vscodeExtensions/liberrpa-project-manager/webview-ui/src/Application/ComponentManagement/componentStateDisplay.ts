// FileName: componentStateDisplay.ts

import type {
  Str_ProjectDependency_LockState,
  Str_ProjectDependency_ComponentsState,
  Str_ProjectDependency_EnvironmentState,
  Str_ProjectDependency_RepairState,
} from "../../Domain/ComponentManagement/componentManagementTypes";

export const COMPONENT_STATE_DISPLAY: Record<
  | Str_ProjectDependency_LockState
  | Str_ProjectDependency_ComponentsState
  | Str_ProjectDependency_EnvironmentState
  | Str_ProjectDependency_RepairState,
  { label: string; color: "success" | "warning" | "error" | undefined }
> = {
  notRequired: { label: "Not required", color: "success" },
  missing: { label: "Missing", color: "error" },
  invalid: { label: "Invalid", color: "error" },
  stale: { label: "Out of date", color: "error" },
  valid: { label: "Valid", color: "success" },
  unverified: { label: "Not verified", color: "warning" },
  damaged: { label: "Damaged", color: "error" },
  unknown: { label: "Unknown", color: "warning" },
  compatible: { label: "Compatible", color: "success" },
  incompatible: { label: "Incompatible", color: "error" },
  notApplicable: { label: "Not applicable", color: undefined },
  available: { label: "Available", color: "warning" },
  repositoryUnavailable: { label: "Repository unavailable", color: "error" },
  wheelMissing: { label: "Wheel missing", color: "error" },
  wheelHashMismatch: { label: "Wheel checksum mismatch", color: "error" },
};
