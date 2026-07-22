// FileName: extensionMessages.ts

export type Theme = "light" | "dark";

export type ProjectType = "flow" | "component";

export interface DictCreateProjectInput {
  templateName: string;
  projectType: ProjectType;

  targetFolder: string;
  projectFolderName: string;

  packageName: string;
  displayName: string;
  version: string;
  description: string;
}

export interface DictProjectTemplateInfo {
  templateName: string;
  projectType: ProjectType;

  defaultVersion: string;
  defaultDescription: string;
}

export type DictMessage_WebviewToExtension =
  | { command: "ready" }
  | { command: "selectTargetFolder" }
  | { command: "confirmCreateProject"; input: DictCreateProjectInput }
  | { command: "cancel" };

export interface DictCreateProjectInitialData {
  templates: DictProjectTemplateInfo[];
  theme: Theme;
}

type DictMessage_ExtensionToWebview =
  | {
      command: "loadCreateProject";
      initialData: DictCreateProjectInitialData;
    }
  | { command: "targetFolderSelected"; path: string }
  | { command: "setBusy"; busy: boolean }
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

export function isMessage_ExtensionToWebview(
  value: unknown,
): value is DictMessage_ExtensionToWebview {
  if (!isRecord(value) || typeof value["command"] !== "string") {
    return false;
  }

  switch (value["command"]) {
    case "loadCreateProject":
      return isCreateProjectLoadInitialData(value["initialData"]);

    case "targetFolderSelected":
      return typeof value["path"] === "string";

    case "setBusy":
      return typeof value["busy"] === "boolean";

    case "error":
      return typeof value["message"] === "string";

    case "themeChanged":
      return value["theme"] === "light" || value["theme"] === "dark";

    default:
      return false;
  }
}
