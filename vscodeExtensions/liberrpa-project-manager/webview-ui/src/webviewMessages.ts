// FileName: webviewMessages.ts
// Keep this file synchronized with:
// - src/webviewMessages.ts
// - webview-ui/src/webviewMessages.ts

export type ProjectType = "flow" | "component";
export type ProjectManagerOperation = "createProject";
export type ProjectManagerTheme = "light" | "dark";

export interface ProjectTemplateInfo {
  templateName: string;
  projectType: ProjectType;
  version: string;
  description: string;
}

export interface CreateProjectInput {
  templateName: string;
  projectType: ProjectType;
  targetFolder: string;
  projectFolderName: string;
  version: string;
  description: string;
  packageName: string;
  displayName: string;
}

export interface CreateProjectLoadContext {
  templates: ProjectTemplateInfo[];
  theme: ProjectManagerTheme;
}

export type WebviewToExtensionMessage =
  | { command: "ready" }
  | { command: "selectTargetFolder" }
  | { command: "confirmCreateProject"; input: CreateProjectInput }
  | { command: "cancel" };

export type ExtensionToWebviewMessage =
  | {
      command: "load";
      operation: "createProject";
      context: CreateProjectLoadContext;
    }
  | { command: "targetFolderSelected"; path: string }
  | { command: "setBusy"; busy: boolean }
  | {
      command: "completed";
      message: string;
      projectPath: string;
      warnings: string[];
    }
  | { command: "error"; message: string }
  | { command: "themeChanged"; theme: ProjectManagerTheme };

export function isWebviewToExtensionMessage(
  value: unknown,
): value is WebviewToExtensionMessage {
  if (!isRecord(value) || typeof value["command"] !== "string") {
    return false;
  }

  switch (value["command"]) {
    case "ready":
    case "selectTargetFolder":
    case "cancel":
      return true;

    case "confirmCreateProject":
      return isCreateProjectInput(value["input"]);

    default:
      return false;
  }
}

export function isExtensionToWebviewMessage(
  value: unknown,
): value is ExtensionToWebviewMessage {
  if (!isRecord(value) || typeof value["command"] !== "string") {
    return false;
  }

  switch (value["command"]) {
    case "load":
      return (
        value["operation"] === "createProject" &&
        isCreateProjectLoadContext(value["context"])
      );

    case "targetFolderSelected":
      return typeof value["path"] === "string";

    case "setBusy":
      return typeof value["busy"] === "boolean";

    case "completed":
      return (
        typeof value["message"] === "string" &&
        typeof value["projectPath"] === "string" &&
        isStringArray(value["warnings"])
      );

    case "error":
      return typeof value["message"] === "string";

    case "themeChanged":
      return value["theme"] === "light" || value["theme"] === "dark";

    default:
      return false;
  }
}

function isCreateProjectInput(value: unknown): value is CreateProjectInput {
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

function isCreateProjectLoadContext(value: unknown): value is CreateProjectLoadContext {
  return (
    isRecord(value) &&
    Array.isArray(value["templates"]) &&
    value["templates"].every(isProjectTemplateInfo) &&
    (value["theme"] === "light" || value["theme"] === "dark")
  );
}

function isProjectTemplateInfo(value: unknown): value is ProjectTemplateInfo {
  return (
    isRecord(value) &&
    typeof value["templateName"] === "string" &&
    (value["projectType"] === "flow" || value["projectType"] === "component") &&
    typeof value["version"] === "string" &&
    typeof value["description"] === "string"
  );
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
