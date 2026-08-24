import fs from "fs";
import path from "path";

import {
  ensureBoolean,
  ensureCustomProjectArgs,
  ensureExactRecord,
  ensureLogLevel,
  ensureRecord,
  ensureString,
  ensureTrimmedSingleLineString,
} from "../Common/validation";
import { DEFAULT_PYTHON_ENVIRONMENT_NAME } from "../Config/environment";
import type { DictProjectCreate } from "../../shared/project";
import type { TypeCustomProjectArgs, TypeLogLevel } from "../../shared/runOptions";

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
  logLevel: TypeLogLevel;
  recordVideo: boolean;
  stopShortcut: boolean;
  highlightUi: boolean;
  customPrjArgs: TypeCustomProjectArgs;
}

export interface DictProjectPackageMetadata {
  name: string;
  version: string;
  projectDetail: DictProjectCreate;
}

const STR_FLOW_MANIFEST_FILE_NAME = "flow.json";
const STR_PACKAGE_MANIFEST_FILE_NAME = ".liberrpa-package.json";
const STR_PROJECT_FLOW_FILE_NAME = "project.flow";
const STR_LEGACY_PROJECT_FILE_NAME = "project.json";

function readJsonFile(strFilePath: string): unknown {
  try {
    return JSON.parse(fs.readFileSync(strFilePath, { encoding: "utf-8" }));
  } catch (e: unknown) {
    throw new Error(`Failed to read JSON file: ${strFilePath}`, { cause: e });
  }
}

function parseFlowManifest(value: unknown): DictFlowManifest {
  const dictManifest = ensureExactRecord(
    value,
    [
      "schemaVersion",
      "name",
      "version",
      "description",
      "requiresLiberrpa",
      "componentDependencies",
    ],
    "flow.json",
  );
  if (dictManifest.schemaVersion !== 1) {
    throw new Error("Only flow.json schemaVersion 1 is supported.");
  }

  const dictRawDependency = ensureRecord(
    dictManifest.componentDependencies,
    "flow.json componentDependencies",
  );
  const dictDependency: Record<string, string> = {};
  for (const [strComponentId, dependencyValue] of Object.entries(dictRawDependency)) {
    if (typeof dependencyValue !== "string") {
      throw new Error(
        `flow.json componentDependencies.${strComponentId} must be a string.`,
      );
    }
    dictDependency[strComponentId] = dependencyValue;
  }

  return {
    schemaVersion: 1,
    name: ensureTrimmedSingleLineString(dictManifest.name, "flow.json name"),
    version: ensureTrimmedSingleLineString(dictManifest.version, "flow.json version"),
    description: ensureString(dictManifest.description, "flow.json description"),
    requiresLiberrpa: ensureTrimmedSingleLineString(
      dictManifest.requiresLiberrpa,
      "flow.json requiresLiberrpa",
    ),
    componentDependencies: dictDependency,
  };
}

function parsePackageManifest(value: unknown): DictPackageManifest {
  const dictManifest = ensureExactRecord(
    value,
    ["schemaVersion", "versionSummary"],
    ".liberrpa-package.json",
  );
  if (dictManifest.schemaVersion !== 1) {
    throw new Error("Only Package manifest schemaVersion 1 is supported.");
  }
  return {
    schemaVersion: 1,
    versionSummary: ensureTrimmedSingleLineString(
      dictManifest.versionSummary,
      ".liberrpa-package.json versionSummary",
      true,
    ),
  };
}

function parseCustomProjectArguments(value: unknown): TypeCustomProjectArgs {
  return ensureCustomProjectArgs(value, "project.flow customPrjArgs");
}

function parseProjectFlowRuntimeSettings(value: unknown): DictProjectFlowRuntimeSettings {
  const dictFlow = ensureExactRecord(
    value,
    [
      "nodes",
      "edges",
      "executeMode",
      "logLevel",
      "recordVideo",
      "stopShortcut",
      "highlightUi",
      "customPrjArgs",
    ],
    "project.flow",
  );
  if (!Array.isArray(dictFlow.nodes) || !Array.isArray(dictFlow.edges)) {
    throw new Error("project.flow nodes and edges must be arrays.");
  }
  if (dictFlow.executeMode !== "Run" && dictFlow.executeMode !== "Debug") {
    throw new Error("project.flow executeMode must be Run or Debug.");
  }
  const strLogLevel = ensureLogLevel(dictFlow.logLevel, "project.flow logLevel");
  return {
    logLevel: strLogLevel,
    recordVideo: ensureBoolean(dictFlow.recordVideo, "project.flow recordVideo"),
    stopShortcut: ensureBoolean(dictFlow.stopShortcut, "project.flow stopShortcut"),
    highlightUi: ensureBoolean(dictFlow.highlightUi, "project.flow highlightUi"),
    customPrjArgs: parseCustomProjectArguments(dictFlow.customPrjArgs),
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
): DictProjectCreate {
  return {
    name: flowManifest.name,
    version: flowManifest.version,
    description: flowManifest.description,
    version_summary: packageManifest.versionSummary,
    python_environment_name: DEFAULT_PYTHON_ENVIRONMENT_NAME,
    timeout_min: 0,
    builtin_log_level: runtimeSettings.logLevel,
    builtin_record_video: runtimeSettings.recordVideo,
    builtin_stop_shortcut: runtimeSettings.stopShortcut,
    builtin_highlight_ui: runtimeSettings.highlightUi,
    custom_prj_args: runtimeSettings.customPrjArgs,
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
