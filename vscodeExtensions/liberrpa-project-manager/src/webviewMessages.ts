// FileName: webviewMessages.ts

import { isRecord, hasExactKeys } from "./typeCheck";
import type {
  Str_ProjectType,
  DictProtocolDependencyOperation,
  DictProtocolResult_RepositoryCatalog,
  DictProtocolResult_ProjectDependencyState,
  DictProtocolResult_ProjectDependencyPlan,
} from "./componentManagement/protocol";

export type Theme = "light" | "dark";

// TODO: Add packageProject later.
export type ProjectManagerOperation = "createProject" | "manageComponents";

export interface DictCreateProjectInput {
  templateName: string;
  projectType: Str_ProjectType;

  targetFolder: string;
  projectFolderName: string;

  packageName: string;
  displayName: string;
  version: string;
  description: string;
}

export interface DictProjectTemplateInfo {
  templateName: string;
  projectType: Str_ProjectType;

  // These data comes from component.json or flow.json.
  defaultVersion: string;
  defaultDescription: string;
}

export type DictMessage_WebviewToExtension =
  | { command: "ready" }
  | { command: "selectTargetFolder" }
  | { command: "confirmCreateProject"; input: DictCreateProjectInput }
  | {
      command: "buildProjectDependencyPlan";
      dependencyOperation: DictProtocolDependencyOperation;
    }
  | {
      command: "applyProjectDependencyPlan";
      dependencyOperation: DictProtocolDependencyOperation;
      confirmedPlanSha256: string;
    }
  | { command: "repairProjectComponents" }
  | { command: "refreshManageComponents" }
  | { command: "cancel" };

interface DictCreateProjectInitialData {
  templates: DictProjectTemplateInfo[];
  theme: Theme;
}

export interface DictManageComponentsNotification {
  type: "info" | "warning";
  message: string;
}

export interface DictManageComponentsInitialData {
  theme: Theme;
  projectState: DictProtocolResult_ProjectDependencyState;
  repositoryCatalog: DictProtocolResult_RepositoryCatalog;
  warningMessages: string[];
  notification?: DictManageComponentsNotification;
}

export type DictMessage_ExtensionToWebview =
  | {
      command: "loadCreateProject";
      initialData: DictCreateProjectInitialData;
    }
  | {
      command: "loadManageComponents";
      initialData: DictManageComponentsInitialData;
    }
  | {
      command: "projectDependencyPlanBuilt";
      dependencyOperation: DictProtocolDependencyOperation;
      plan: DictProtocolResult_ProjectDependencyPlan;
      warningMessages: string[];
    }
  | { command: "targetFolderSelected"; path: string }
  | { command: "setBusy"; busy: boolean }
  | { command: "componentManagementError"; code: string; message: string }
  | { command: "error"; message: string }
  | { command: "themeChanged"; theme: Theme };

function isCreateProjectInput(value: unknown): value is DictCreateProjectInput {
  return (
    isRecord(value) &&
    typeof value["templateName"] === "string" &&
    (value["projectType"] === "flow" || value["projectType"] === "component") &&
    typeof value["targetFolder"] === "string" &&
    typeof value["projectFolderName"] === "string" &&
    typeof value["version"] === "string" &&
    typeof value["description"] === "string" &&
    typeof value["packageName"] === "string" &&
    typeof value["displayName"] === "string"
  );
}

function isDependencyOperation(value: unknown): value is DictProtocolDependencyOperation {
  if (!isRecord(value)) {
    return false;
  }

  switch (value["operation"]) {
    case "addComponentDependency":
    case "changeComponentRequirement":
      return (
        hasExactKeys(value, new Set(["operation", "componentId", "requirement"])) &&
        typeof value["componentId"] === "string" &&
        typeof value["requirement"] === "string"
      );

    case "updateComponents":
      return (
        hasExactKeys(value, new Set(["operation", "componentIds"])) &&
        Array.isArray(value["componentIds"]) &&
        value["componentIds"].every((componentId) => typeof componentId === "string")
      );

    case "removeComponentDependency":
      return (
        hasExactKeys(value, new Set(["operation", "componentId"])) &&
        typeof value["componentId"] === "string"
      );

    default:
      return false;
  }
}

export function isMessage_WebviewToExtension(
  value: unknown,
): value is DictMessage_WebviewToExtension {
  if (!isRecord(value) || typeof value["command"] !== "string") {
    return false;
  }

  switch (value["command"]) {
    case "ready":
    case "selectTargetFolder":
    case "repairProjectComponents":
    case "refreshManageComponents":
    case "cancel":
      return true;

    case "confirmCreateProject":
      return isCreateProjectInput(value["input"]);

    case "buildProjectDependencyPlan":
      return isDependencyOperation(value["dependencyOperation"]);

    case "applyProjectDependencyPlan":
      return (
        isDependencyOperation(value["dependencyOperation"]) &&
        typeof value["confirmedPlanSha256"] === "string"
      );

    default:
      return false;
  }
}
