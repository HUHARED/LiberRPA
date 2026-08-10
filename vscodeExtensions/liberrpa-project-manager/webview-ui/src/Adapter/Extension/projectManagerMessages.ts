// FileName: projectManagerMessages.ts
// IMPORTANT: Keep the Extension and Webview copies of this file synchronized.
// Synchronization is verified by scripts/checkSynchronizedFiles.mjs.
// - src/Adapter/Webview/projectManagerMessages.ts
// - webview-ui/src/Adapter/Extension/projectManagerMessages.ts

import {
  isRecord,
  isStringRecord,
  isStringArray,
  hasExactKeys,
  isNonNegativeInteger,
} from "../../Common/typeCheck";
import type {
  DictProtocolDependencyOperation,
  DictProtocolResult_Publish,
  DictProtocolResult_RepositoryCatalog,
  DictProtocolResult_ProjectDependencyState,
  DictProtocolResult_ProjectDependencyPlan,
} from "../../Domain/ComponentManagement/componentManagementTypes";
import type {
  DictProjectManifest_Component,
  DictCreateProjectInput,
  DictProjectTemplateInfo,
} from "../../Domain/Project/projectTypes";

export type Theme = "light" | "dark";
// TODO: Add packageProject later.
export type ProjectManagerOperation =
  | "createProject"
  | "publishComponent"
  | "manageComponents";
export type Str_PublishComponentFile = "astSnippets" | "snippetsConfig";

export interface DictProjectManagerNotification {
  type: "info" | "warning";
  message: string;
}

export interface DictCreateProjectInitialData {
  templates: DictProjectTemplateInfo[];
  theme: Theme;
}

export interface DictPublishComponentInitialData {
  theme: Theme;
  projectPath: string;
  manifest: DictProjectManifest_Component;

  astSnippetsFile: string;
  snippetsJsoncFile: string;
  astSnippetsFileExists: boolean;
  snippetsJsoncFileExists: boolean;

  publishResult: DictProtocolResult_Publish | null;
  warningMessages: string[];
  notification?: DictProjectManagerNotification;
}

export interface DictManageComponentsInitialData {
  theme: Theme;
  projectState: DictProtocolResult_ProjectDependencyState;
  repositoryCatalog: DictProtocolResult_RepositoryCatalog;
  warningMessages: string[];
  notification?: DictProjectManagerNotification;
}

export type DictMessage_WebviewToExtension =
  | { command: "ready" }
  | { command: "selectTargetFolder" }
  | { command: "confirmCreateProject"; input: DictCreateProjectInput }
  | { command: "runPublishComponent" }
  | { command: "refreshPublishComponent" }
  | {
      command: "openPublishComponentFile";
      file: Str_PublishComponentFile;
    }
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
      command: "loadPublishComponent";
      initialData: DictPublishComponentInitialData;
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

const SET_COMPONENT_MANIFEST_KEYS = new Set([
  "schemaVersion",
  "id",
  "packageName",
  "displayName",
  "version",
  "description",
  "requiresLiberrpa",
  "componentDependencies",
]);
const SET_PUBLISH_RESULT_BASE_KEYS = new Set([
  "status",
  "componentId",
  "packageName",
  "astSnippetsFile",
  "snippetsJsoncFile",
  "generatedCount",
  "skippedCount",
  "warningCount",
]);
const SET_PUBLISH_RESULT_PUBLISHED_KEYS = new Set([
  ...SET_PUBLISH_RESULT_BASE_KEYS,
  "version",
  "excludedCount",
  "handWrittenCount",
  "finalCount",
  "wheelFileName",
  "sha256",
]);

function isTheme(value: unknown): value is Theme {
  return value === "light" || value === "dark";
}

function isProjectManagerNotification(
  value: unknown,
): value is DictProjectManagerNotification {
  return (
    isRecord(value) &&
    hasExactKeys(value, new Set(["type", "message"])) &&
    (value["type"] === "info" || value["type"] === "warning") &&
    typeof value["message"] === "string"
  );
}

function isComponentManifest(value: unknown): value is DictProjectManifest_Component {
  return (
    isRecord(value) &&
    hasExactKeys(value, SET_COMPONENT_MANIFEST_KEYS) &&
    value["schemaVersion"] === 1 &&
    typeof value["id"] === "string" &&
    typeof value["packageName"] === "string" &&
    typeof value["displayName"] === "string" &&
    typeof value["version"] === "string" &&
    typeof value["description"] === "string" &&
    typeof value["requiresLiberrpa"] === "string" &&
    isStringRecord(value["componentDependencies"])
  );
}

function isPublishResultBase(value: Record<string, unknown>): boolean {
  return (
    typeof value["componentId"] === "string" &&
    typeof value["packageName"] === "string" &&
    typeof value["astSnippetsFile"] === "string" &&
    typeof value["snippetsJsoncFile"] === "string" &&
    isNonNegativeInteger(value["generatedCount"]) &&
    isNonNegativeInteger(value["skippedCount"]) &&
    isNonNegativeInteger(value["warningCount"])
  );
}

function isPublishResult(value: unknown): value is DictProtocolResult_Publish {
  if (!isRecord(value) || typeof value["status"] !== "string") {
    return false;
  }

  if (value["status"] === "preparationCreated") {
    return hasExactKeys(value, SET_PUBLISH_RESULT_BASE_KEYS) && isPublishResultBase(value);
  }

  return (
    (value["status"] === "published" || value["status"] === "alreadyPublished") &&
    hasExactKeys(value, SET_PUBLISH_RESULT_PUBLISHED_KEYS) &&
    isPublishResultBase(value) &&
    typeof value["version"] === "string" &&
    isNonNegativeInteger(value["excludedCount"]) &&
    isNonNegativeInteger(value["handWrittenCount"]) &&
    isNonNegativeInteger(value["finalCount"]) &&
    typeof value["wheelFileName"] === "string" &&
    typeof value["sha256"] === "string" &&
    /^[0-9a-f]{64}$/.test(value["sha256"])
  );
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
        isStringArray(value["componentIds"])
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

function isPublishComponentInitialData(
  value: unknown,
): value is DictPublishComponentInitialData {
  if (!isRecord(value)) {
    return false;
  }

  const setRequiredKey = new Set([
    "theme",
    "projectPath",
    "manifest",
    "astSnippetsFile",
    "snippetsJsoncFile",
    "astSnippetsFileExists",
    "snippetsJsoncFileExists",
    "publishResult",
    "warningMessages",
  ]);
  const setAllowedKey =
    value["notification"] === undefined
      ? setRequiredKey
      : new Set([...setRequiredKey, "notification"]);

  return (
    hasExactKeys(value, setAllowedKey) &&
    isTheme(value["theme"]) &&
    typeof value["projectPath"] === "string" &&
    isComponentManifest(value["manifest"]) &&
    typeof value["astSnippetsFile"] === "string" &&
    typeof value["snippetsJsoncFile"] === "string" &&
    typeof value["astSnippetsFileExists"] === "boolean" &&
    typeof value["snippetsJsoncFileExists"] === "boolean" &&
    (value["publishResult"] === null || isPublishResult(value["publishResult"])) &&
    isStringArray(value["warningMessages"]) &&
    (value["notification"] === undefined ||
      isProjectManagerNotification(value["notification"]))
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
      isProjectManagerNotification(value["notification"]))
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
    case "runPublishComponent":
    case "refreshPublishComponent":
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

    case "openPublishComponentFile":
      return (
        hasExactKeys(value, new Set(["command", "file"])) &&
        (value["file"] === "astSnippets" || value["file"] === "snippetsConfig")
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

    case "loadPublishComponent":
      return (
        hasExactKeys(value, new Set(["command", "initialData"])) &&
        isPublishComponentInitialData(value["initialData"])
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
