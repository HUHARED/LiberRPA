import fs from "fs";
import path from "path";

import { ensureLogLevel, isRecord } from "../Common/validation";
import { DEFAULT_PYTHON_ENVIRONMENT_NAME } from "../Config/environment";
import type {
  TypeColumns_LogLevel,
  TypeCustomProjectArgs,
  DictColumns_Project_Detail_ToInsert,
} from "../../shared/interface";

interface DictFlowManifest {
  schemaVersion: 1;
  name: string;
  version: string;
  description: string;
  requiresLiberrpa: string;
  componentDependencies: Record<string, string>;
}

interface DictPackageManifest {
  schemaVersion: 1;
  versionSummary: string;
}

interface DictProjectFlowRuntimeSettings {
  logLevel: TypeColumns_LogLevel;
  recordVideo: boolean;
  stopShortcut: boolean;
  highlightUi: boolean;
  customPrjArgs: TypeCustomProjectArgs;
}

export interface DictProjectPackageMetadata {
  name: string;
  version: string;
  projectDetail: DictColumns_Project_Detail_ToInsert;
}

const STR_FLOW_MANIFEST_FILE_NAME = "flow.json";
const STR_PACKAGE_MANIFEST_FILE_NAME = ".liberrpa-package.json";
const STR_PROJECT_FLOW_FILE_NAME = "project.flow";
const STR_LEGACY_PROJECT_FILE_NAME = "project.json";
const SET_FLOW_MANIFEST_KEYS = new Set([
  "schemaVersion",
  "name",
  "version",
  "description",
  "requiresLiberrpa",
  "componentDependencies",
]);
const SET_PACKAGE_MANIFEST_KEYS = new Set(["schemaVersion", "versionSummary"]);
const SET_PROJECT_FLOW_KEYS = new Set([
  "nodes",
  "edges",
  "executeMode",
  "logLevel",
  "recordVideo",
  "stopShortcut",
  "highlightUi",
  "customPrjArgs",
]);

function hasExactKeys(
  value: Record<string, unknown>,
  setExpectedKey: Set<string>,
): boolean {
  const arrKey = Object.keys(value);
  return (
    arrKey.length === setExpectedKey.size &&
    arrKey.every((strKey) => setExpectedKey.has(strKey))
  );
}

function readJsonFile(strFilePath: string): unknown {
  try {
    return JSON.parse(fs.readFileSync(strFilePath, { encoding: "utf-8" }));
  } catch (e: unknown) {
    throw new Error(`Failed to read JSON file: ${strFilePath}`, { cause: e });
  }
}

function validateTrimmedSingleLine(
  value: unknown,
  strFieldName: string,
  boolAllowEmpty: boolean,
): string {
  if (typeof value !== "string") {
    throw new Error(`${strFieldName} must be a string.`);
  }
  if ((!boolAllowEmpty && value.length === 0) || value !== value.trim()) {
    throw new Error(
      boolAllowEmpty
        ? `${strFieldName} cannot start or end with whitespace.`
        : `${strFieldName} must be a non-empty trimmed string.`,
    );
  }
  if (value.includes("\r") || value.includes("\n")) {
    throw new Error(`${strFieldName} must be a single line.`);
  }
  return value;
}

function parseFlowManifest(value: unknown): DictFlowManifest {
  if (!isRecord(value) || !hasExactKeys(value, SET_FLOW_MANIFEST_KEYS)) {
    throw new Error("flow.json contains missing or unknown fields.");
  }
  if (value.schemaVersion !== 1) {
    throw new Error("Only flow.json schemaVersion 1 is supported.");
  }
  if (!isRecord(value.componentDependencies)) {
    throw new Error("flow.json componentDependencies must be an object.");
  }
  const dictDependency: Record<string, string> = {};
  for (const [strComponentId, dependencyValue] of Object.entries(
    value.componentDependencies,
  )) {
    if (typeof dependencyValue !== "string") {
      throw new Error(
        `flow.json componentDependencies.${strComponentId} must be a string.`,
      );
    }
    dictDependency[strComponentId] = dependencyValue;
  }

  if (typeof value.description !== "string") {
    throw new Error("flow.json description must be a string.");
  }

  return {
    schemaVersion: 1,
    name: validateTrimmedSingleLine(value.name, "flow.json name", false),
    version: validateTrimmedSingleLine(value.version, "flow.json version", false),
    description: value.description,
    requiresLiberrpa: validateTrimmedSingleLine(
      value.requiresLiberrpa,
      "flow.json requiresLiberrpa",
      false,
    ),
    componentDependencies: dictDependency,
  };
}

function parsePackageManifest(value: unknown): DictPackageManifest {
  if (!isRecord(value) || !hasExactKeys(value, SET_PACKAGE_MANIFEST_KEYS)) {
    throw new Error(".liberrpa-package.json contains missing or unknown fields.");
  }
  if (value.schemaVersion !== 1) {
    throw new Error("Only Package manifest schemaVersion 1 is supported.");
  }
  return {
    schemaVersion: 1,
    versionSummary: validateTrimmedSingleLine(
      value.versionSummary,
      ".liberrpa-package.json versionSummary",
      true,
    ),
  };
}

function parseCustomProjectArguments(value: unknown): TypeCustomProjectArgs {
  if (!Array.isArray(value)) {
    throw new Error("project.flow customPrjArgs must be an array.");
  }

  const setKey = new Set<string>();
  return value.map((item, intIndex) => {
    if (!Array.isArray(item) || item.length !== 2) {
      throw new Error(
        `project.flow customPrjArgs[${String(intIndex)}] must contain a key and value.`,
      );
    }
    const strKey = validateTrimmedSingleLine(
      item[0],
      `project.flow customPrjArgs[${String(intIndex)}][0]`,
      false,
    );
    if (setKey.has(strKey)) {
      throw new Error(`Duplicate Custom Project Argument key: ${strKey}`);
    }
    setKey.add(strKey);
    return [strKey, item[1]];
  });
}

function parseProjectFlowRuntimeSettings(value: unknown): DictProjectFlowRuntimeSettings {
  if (!isRecord(value) || !hasExactKeys(value, SET_PROJECT_FLOW_KEYS)) {
    throw new Error("project.flow contains missing or unknown root fields.");
  }
  if (!Array.isArray(value.nodes) || !Array.isArray(value.edges)) {
    throw new Error("project.flow nodes and edges must be arrays.");
  }
  if (value.executeMode !== "Run" && value.executeMode !== "Debug") {
    throw new Error("project.flow executeMode must be Run or Debug.");
  }
  const strLogLevel = ensureLogLevel(value.logLevel, "project.flow logLevel");
  if (
    typeof value.recordVideo !== "boolean" ||
    typeof value.stopShortcut !== "boolean" ||
    typeof value.highlightUi !== "boolean"
  ) {
    throw new Error(
      "project.flow recordVideo, stopShortcut and highlightUi must be Boolean values.",
    );
  }

  return {
    logLevel: strLogLevel,
    recordVideo: value.recordVideo,
    stopShortcut: value.stopShortcut,
    highlightUi: value.highlightUi,
    customPrjArgs: parseCustomProjectArguments(value.customPrjArgs),
  };
}

function readRequiredRootJson(strProjectPath: string, strFileName: string): unknown {
  const strFilePath = path.join(strProjectPath, strFileName);
  if (!fs.existsSync(strFilePath) || !fs.statSync(strFilePath).isFile()) {
    throw new Error(`The Package does not contain ${strFileName} at its root.`);
  }
  return readJsonFile(strFilePath);
}

function buildProjectDetail(
  flowManifest: DictFlowManifest,
  packageManifest: DictPackageManifest,
  runtimeSettings: DictProjectFlowRuntimeSettings,
): DictColumns_Project_Detail_ToInsert {
  return {
    name: flowManifest.name,
    version: flowManifest.version,
    description: flowManifest.description,
    version_summary: packageManifest.versionSummary,
    python_environment_name: DEFAULT_PYTHON_ENVIRONMENT_NAME,
    timeout_min: 0,
    builtin_log_level: runtimeSettings.logLevel,
    builtin_record_video: runtimeSettings.recordVideo ? 1 : 0,
    builtin_stop_shortcut: runtimeSettings.stopShortcut ? 1 : 0,
    builtin_highlight_ui: runtimeSettings.highlightUi ? 1 : 0,
    custom_prj_args: JSON.stringify(runtimeSettings.customPrjArgs),
  };
}

export function readProjectPackageMetadata(
  strProjectPath: string,
): DictProjectPackageMetadata {
  const strLegacyProjectPath = path.join(strProjectPath, STR_LEGACY_PROJECT_FILE_NAME);
  if (fs.existsSync(strLegacyProjectPath)) {
    throw new Error(
      "This is a legacy project.json Package. Create a new Package with the current Project Manager.",
    );
  }

  const flowManifest = parseFlowManifest(
    readRequiredRootJson(strProjectPath, STR_FLOW_MANIFEST_FILE_NAME),
  );
  const packageManifest = parsePackageManifest(
    readRequiredRootJson(strProjectPath, STR_PACKAGE_MANIFEST_FILE_NAME),
  );
  const runtimeSettings = parseProjectFlowRuntimeSettings(
    readRequiredRootJson(strProjectPath, STR_PROJECT_FLOW_FILE_NAME),
  );

  return {
    name: flowManifest.name,
    version: flowManifest.version,
    projectDetail: buildProjectDetail(flowManifest, packageManifest, runtimeSettings),
  };
}
