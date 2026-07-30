// FileName: extensionMessages.ts

import type {
  Str_ProjectType,
  DictProtocolDependencyOperation,
  DictProtocolResult_RepositoryCatalog,
  DictProtocolResult_ProjectDependencyState,
  DictProtocolResult_ProjectDependencyPlan,
} from "./componentManagement/protocol";

export type Theme = "light" | "dark";
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

export interface DictCreateProjectInitialData {
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isProjectTemplateInfo(value: unknown): value is DictProjectTemplateInfo {
  return (
    isRecord(value) &&
    typeof value["templateName"] === "string" &&
    (value["projectType"] === "flow" || value["projectType"] === "component") &&
    typeof value["defaultVersion"] === "string" &&
    typeof value["defaultDescription"] === "string"
  );
}

function isCreateProjectLoadInitialData(
  value: unknown,
): value is DictCreateProjectInitialData {
  return (
    isRecord(value) &&
    Array.isArray(value["templates"]) &&
    value["templates"].every(isProjectTemplateInfo) &&
    (value["theme"] === "light" || value["theme"] === "dark")
  );
}

function isManageComponentsInitialData(
  value: unknown,
): value is DictManageComponentsInitialData {
  if (
    !isRecord(value) ||
    (value["theme"] !== "light" && value["theme"] !== "dark") ||
    !isRecord(value["projectState"]) ||
    value["projectState"]["status"] !== "projectDependencyState" ||
    !isRecord(value["repositoryCatalog"]) ||
    value["repositoryCatalog"]["status"] !== "componentRepositoryCatalog" ||
    !Array.isArray(value["warningMessages"]) ||
    !value["warningMessages"].every((item) => typeof item === "string")
  ) {
    return false;
  }

  const notification = value["notification"];
  return (
    notification === undefined ||
    (isRecord(notification) &&
      (notification["type"] === "info" || notification["type"] === "warning") &&
      typeof notification["message"] === "string")
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
        typeof value["componentId"] === "string" && typeof value["requirement"] === "string"
      );

    case "updateComponents":
      return (
        Array.isArray(value["componentIds"]) &&
        value["componentIds"].every((componentId) => typeof componentId === "string")
      );

    case "removeComponentDependency":
      return typeof value["componentId"] === "string";

    default:
      return false;
  }
}

function isProjectDependencyPlan(
  value: unknown,
): value is DictProtocolResult_ProjectDependencyPlan {
  return (
    isRecord(value) &&
    value["status"] === "projectDependencyPlanCreated" &&
    typeof value["planSha256"] === "string" &&
    Array.isArray(value["directDependencyChanges"]) &&
    Array.isArray(value["resolvedComponentChanges"])
  );
}

export function isMessage_ExtensionToWebview(
  value: unknown,
): value is DictMessage_ExtensionToWebview {
  if (!isRecord(value) || typeof value["command"] !== "string") {
    return false;
  }

  switch (value["command"]) {
    case "loadCreateProject":
      return isCreateProjectLoadInitialData(value["initialData"]);

    case "loadManageComponents":
      return isManageComponentsInitialData(value["initialData"]);

    case "projectDependencyPlanBuilt":
      return (
        isDependencyOperation(value["dependencyOperation"]) &&
        isProjectDependencyPlan(value["plan"]) &&
        Array.isArray(value["warningMessages"]) &&
        value["warningMessages"].every((item) => typeof item === "string")
      );

    case "targetFolderSelected":
      return typeof value["path"] === "string";

    case "setBusy":
      return typeof value["busy"] === "boolean";

    case "componentManagementError":
      return typeof value["code"] === "string" && typeof value["message"] === "string";

    case "error":
      return typeof value["message"] === "string";

    case "themeChanged":
      return value["theme"] === "light" || value["theme"] === "dark";

    default:
      return false;
  }
}
