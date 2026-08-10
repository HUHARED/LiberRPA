// FileName: projectManagerMessages.ts
// IMPORTANT: Keep the Extension and Webview copies of this file synchronized.
// Synchronization is verified by scripts/checkSynchronizedFiles.mjs.
// - src/Adapter/Webview/projectManagerMessages.ts
// - webview-ui/src/Adapter/Extension/projectManagerMessages.ts

import { isRecord, isStringArray, hasExactKeys } from "../../Common/typeCheck";
import type {
  DictProtocolDependencyOperation,
  DictProtocolResult_RepositoryCatalog,
  DictProtocolResult_ProjectDependencyState,
  DictProtocolResult_ProjectDependencyPlan,
} from "../../Domain/ComponentManagement/componentManagementTypes";
import type {
  DictCreateProjectInput,
  DictProjectTemplateInfo,
} from "../../Domain/Project/projectTypes";

export type Theme = "light" | "dark";
// TODO: Add packageProject later.
export type ProjectManagerOperation = "createProject" | "manageComponents";

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
  | { command: "importComponentWheels" }
  | { command: "refreshManageComponents" }
  | { command: "cancel" };

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
  | { command: "targetFolderSelected"; targetFolderPath: string }
  | { command: "setBusy"; busy: boolean }
  | {
      command: "componentManagementError";
      code: string;
      message: string;
      details: Record<string, unknown>;
    }
  | { command: "error"; message: string }
  | { command: "themeChanged"; theme: Theme };

function isTheme(value: unknown): value is Theme {
  return value === "light" || value === "dark";
}

function isCreateProjectInput(value: unknown): value is DictCreateProjectInput {
  return (
    isRecord(value) &&
    hasExactKeys(
      value,
      new Set([
        "templateName",
        "projectType",
        "targetFolderPath",
        "projectFolderName",
        "packageName",
        "displayName",
        "version",
        "description",
      ]),
    ) &&
    typeof value["templateName"] === "string" &&
    (value["projectType"] === "flow" || value["projectType"] === "component") &&
    typeof value["targetFolderPath"] === "string" &&
    typeof value["projectFolderName"] === "string" &&
    typeof value["packageName"] === "string" &&
    typeof value["displayName"] === "string" &&
    typeof value["version"] === "string" &&
    typeof value["description"] === "string"
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
  }

  return false;
}

function isProjectTemplateInfo(value: unknown): value is DictProjectTemplateInfo {
  return (
    isRecord(value) &&
    hasExactKeys(
      value,
      new Set(["templateName", "projectType", "defaultVersion", "defaultDescription"]),
    ) &&
    typeof value["templateName"] === "string" &&
    (value["projectType"] === "flow" || value["projectType"] === "component") &&
    typeof value["defaultVersion"] === "string" &&
    typeof value["defaultDescription"] === "string"
  );
}

function isCreateProjectInitialData(value: unknown): value is DictCreateProjectInitialData {
  return (
    isRecord(value) &&
    hasExactKeys(value, new Set(["templates", "theme"])) &&
    Array.isArray(value["templates"]) &&
    value["templates"].every(isProjectTemplateInfo) &&
    isTheme(value["theme"])
  );
}

function isManageComponentsNotification(
  value: unknown,
): value is DictManageComponentsNotification {
  return (
    isRecord(value) &&
    hasExactKeys(value, new Set(["type", "message"])) &&
    (value["type"] === "info" || value["type"] === "warning") &&
    typeof value["message"] === "string"
  );
}

function isManageComponentsInitialData(
  value: unknown,
): value is DictManageComponentsInitialData {
  if (!isRecord(value)) {
    return false;
  }

  const setRequiredKey = new Set([
    "theme",
    "projectState",
    "repositoryCatalog",
    "warningMessages",
  ]);
  const setAllowedKey =
    value["notification"] === undefined
      ? setRequiredKey
      : new Set([...setRequiredKey, "notification"]);

  return (
    hasExactKeys(value, setAllowedKey) &&
    isTheme(value["theme"]) &&
    isRecord(value["projectState"]) &&
    value["projectState"]["status"] === "projectDependencyState" &&
    isRecord(value["repositoryCatalog"]) &&
    value["repositoryCatalog"]["status"] === "componentRepositoryCatalog" &&
    isStringArray(value["warningMessages"]) &&
    (value["notification"] === undefined ||
      isManageComponentsNotification(value["notification"]))
  );
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
    case "importComponentWheels":
    case "refreshManageComponents":
    case "cancel":
      return hasExactKeys(value, new Set(["command"]));

    case "confirmCreateProject":
      return (
        hasExactKeys(value, new Set(["command", "input"])) &&
        isCreateProjectInput(value["input"])
      );

    case "buildProjectDependencyPlan":
      return (
        hasExactKeys(value, new Set(["command", "dependencyOperation"])) &&
        isDependencyOperation(value["dependencyOperation"])
      );

    case "applyProjectDependencyPlan":
      return (
        hasExactKeys(
          value,
          new Set(["command", "dependencyOperation", "confirmedPlanSha256"]),
        ) &&
        isDependencyOperation(value["dependencyOperation"]) &&
        typeof value["confirmedPlanSha256"] === "string" &&
        /^[0-9a-f]{64}$/.test(value["confirmedPlanSha256"])
      );
  }

  return false;
}

export function isMessage_ExtensionToWebview(
  value: unknown,
): value is DictMessage_ExtensionToWebview {
  if (!isRecord(value) || typeof value["command"] !== "string") {
    return false;
  }

  switch (value["command"]) {
    case "loadCreateProject":
      return (
        hasExactKeys(value, new Set(["command", "initialData"])) &&
        isCreateProjectInitialData(value["initialData"])
      );

    case "loadManageComponents":
      return (
        hasExactKeys(value, new Set(["command", "initialData"])) &&
        isManageComponentsInitialData(value["initialData"])
      );

    case "projectDependencyPlanBuilt":
      return (
        hasExactKeys(
          value,
          new Set(["command", "dependencyOperation", "plan", "warningMessages"]),
        ) &&
        isDependencyOperation(value["dependencyOperation"]) &&
        isRecord(value["plan"]) &&
        value["plan"]["status"] === "projectDependencyPlanCreated" &&
        isStringArray(value["warningMessages"])
      );

    case "targetFolderSelected":
      return (
        hasExactKeys(value, new Set(["command", "targetFolderPath"])) &&
        typeof value["targetFolderPath"] === "string"
      );

    case "setBusy":
      return (
        hasExactKeys(value, new Set(["command", "busy"])) &&
        typeof value["busy"] === "boolean"
      );

    case "componentManagementError":
      return (
        hasExactKeys(value, new Set(["command", "code", "message", "details"])) &&
        typeof value["code"] === "string" &&
        typeof value["message"] === "string" &&
        isRecord(value["details"])
      );

    case "error":
      return (
        hasExactKeys(value, new Set(["command", "message"])) &&
        typeof value["message"] === "string"
      );

    case "themeChanged":
      return hasExactKeys(value, new Set(["command", "theme"])) && isTheme(value["theme"]);
  }

  return false;
}
