// FileName: packageMetadata.ts

import { execFile } from "child_process";
import fs from "fs";
import path from "path";
import { promisify } from "util";

import { app } from "electron";

import { readJsonFile } from "../Common/jsonFile";
import {
  ensureRecord,
  ensureExactRecord,
  ensureTrimmedSingleLineString,
  ensurePackageDescription,
  ensureVersionSummary,
  ensureBoolean,
  ensureLogLevel,
  ensureCustomProjectArgs,
} from "../Common/validation";
import {
  STR_DEFAULT_PYTHON_ENVIRONMENT_NAME,
  buildPythonProcessEnvironment,
  getPythonEnvironmentPath,
} from "../Config/environment";
import { getPackageFolderName } from "../FileSystem/executorFiles";
import { INT_MAX_PROJECT_FLOW_BYTES, type PackageCreateData } from "../../shared/package";
import type { CustomProjectArgs, LogLevel } from "../../shared/runSettings";

interface FlowManifest {
  schemaVersion: 1;
  name: string;
  version: string;
  description: string;
  requiresLiberrpa: string;
  componentDependencies: Record<string, string>;
}

interface PackageManifest {
  schemaVersion: 1;
  versionSummary: string;
}

interface ProjectRuntimeSettings {
  logLevel: LogLevel;
  recordVideo: boolean;
  stopShortcut: boolean;
  highlightUi: boolean;
  customPrjArgs: CustomProjectArgs;
}

const execFileAsync = promisify(execFile);
const STR_FLOW_MANIFEST_FILE_NAME = "flow.json";
const STR_PACKAGE_MANIFEST_FILE_NAME = ".liberrpa-package.json";
const STR_PROJECT_FLOW_FILE_NAME = "project.flow";

function parseFlowManifest(value: unknown): FlowManifest {
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
    if (
      !/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(
        strComponentId,
      )
    ) {
      throw new Error(
        "flow.json component dependency IDs must use lowercase UUID v4 format with hyphens.",
      );
    }
    dictDependency[strComponentId] = ensureTrimmedSingleLineString(
      dependencyValue,
      `flow.json componentDependencies.${strComponentId}`,
    );
  }

  return {
    schemaVersion: 1,
    name: ensureTrimmedSingleLineString(dictManifest.name, "flow.json name"),
    version: ensureTrimmedSingleLineString(dictManifest.version, "flow.json version"),
    description: ensurePackageDescription(
      dictManifest.description,
      "flow.json description",
    ),
    requiresLiberrpa: ensureTrimmedSingleLineString(
      dictManifest.requiresLiberrpa,
      "flow.json requiresLiberrpa",
    ),
    componentDependencies: dictDependency,
  };
}

async function validateAndNormalizeFlowVersionMetadata(
  manifest: FlowManifest,
): Promise<string> {
  const strResourcesPath = app.isPackaged
    ? path.join(process.resourcesPath, "app.asar.unpacked/resources")
    : path.join(app.getAppPath(), "resources");
  const strScriptPath = path.join(
    strResourcesPath,
    "pyPackageScript/ValidateVersionMetadata.py",
  );
  const strEnvironmentPath = getPythonEnvironmentPath(STR_DEFAULT_PYTHON_ENVIRONMENT_NAME);
  const promiseResult = execFileAsync(
    path.join(strEnvironmentPath, "python.exe"),
    ["-I", "-X", "utf8", strScriptPath],
    {
      env: buildPythonProcessEnvironment({ pythonEnvironmentPath: strEnvironmentPath }),
      timeout: 15_000,
      maxBuffer: 1024 * 1024,
      windowsHide: true,
    },
  );
  // Use stdin to avoid Windows command-line length limits for dependency metadata.
  promiseResult.child.stdin?.end(
    JSON.stringify({
      version: manifest.version,
      requiresLiberrpa: manifest.requiresLiberrpa,
      componentDependencies: manifest.componentDependencies,
    }),
  );
  const { stdout } = await promiseResult;
  return ensureTrimmedSingleLineString(stdout.trim(), "Normalized flow.json version");
}

function parsePackageManifest(value: unknown): PackageManifest {
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
    versionSummary: ensureVersionSummary(
      dictManifest.versionSummary,
      ".liberrpa-package.json versionSummary",
    ),
  };
}

function parseProjectFlowRuntimeSettings(value: unknown): ProjectRuntimeSettings {
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
    customPrjArgs: ensureCustomProjectArgs(
      dictFlow.customPrjArgs,
      "project.flow customPrjArgs",
    ),
  };
}

function readRequiredRootJson(packagePath: string, fileName: string): unknown {
  const strFilePath = path.join(packagePath, fileName);
  const fileStat = fs.existsSync(strFilePath) ? fs.statSync(strFilePath) : null;
  if (!fileStat?.isFile()) {
    throw new Error(`The Package does not contain ${fileName} at its root.`);
  }
  if (
    fileName === STR_PROJECT_FLOW_FILE_NAME &&
    fileStat.size > INT_MAX_PROJECT_FLOW_BYTES
  ) {
    throw new Error("project.flow exceeds the 8 MiB limit.");
  }
  return readJsonFile(strFilePath, fileName);
}

function buildPackageDetails(
  flowManifest: FlowManifest,
  packageManifest: PackageManifest,
  runtimeSettings: ProjectRuntimeSettings,
): PackageCreateData {
  return {
    project_name: flowManifest.name,
    project_version: flowManifest.version,
    description: flowManifest.description,
    version_summary: packageManifest.versionSummary,
    python_environment_name: STR_DEFAULT_PYTHON_ENVIRONMENT_NAME,
    max_retry_count: 0,
    timeout_min: 0,
    builtin_log_level: runtimeSettings.logLevel,
    builtin_record_video: runtimeSettings.recordVideo,
    builtin_stop_shortcut: runtimeSettings.stopShortcut,
    builtin_highlight_ui: runtimeSettings.highlightUi,
    custom_prj_args: runtimeSettings.customPrjArgs,
  };
}

export async function readPackageMetadata(packagePath: string): Promise<PackageCreateData> {
  const flowManifest = parseFlowManifest(
    readRequiredRootJson(packagePath, STR_FLOW_MANIFEST_FILE_NAME),
  );
  const packageManifest = parsePackageManifest(
    readRequiredRootJson(packagePath, STR_PACKAGE_MANIFEST_FILE_NAME),
  );
  const runtimeSettings = parseProjectFlowRuntimeSettings(
    readRequiredRootJson(packagePath, STR_PROJECT_FLOW_FILE_NAME),
  );

  flowManifest.version = await validateAndNormalizeFlowVersionMetadata(flowManifest);
  getPackageFolderName(flowManifest.name, flowManifest.version);
  return buildPackageDetails(flowManifest, packageManifest, runtimeSettings);
}

export async function validatePackageLiberrpaRequirement(
  packagePath: string,
  pythonEnvironmentPath: string,
): Promise<void> {
  await execFileAsync(
    path.join(pythonEnvironmentPath, "python.exe"),
    [
      "-I",
      "-X",
      "utf8",
      "-c",
      [
        "import importlib.metadata, json, sys",
        "from packaging.specifiers import SpecifierSet",
        "with open(sys.argv[1], encoding='utf-8-sig') as manifestFile:",
        "    dictManifest = json.load(manifestFile)",
        "strVersion = importlib.metadata.version('liberrpa')",
        "strRequirement = dictManifest['requiresLiberrpa']",
        "if strVersion not in SpecifierSet(strRequirement):",
        "    sys.exit(f'Installed liberrpa {strVersion} does not satisfy {strRequirement}')",
      ].join("\n"),
      path.join(packagePath, STR_FLOW_MANIFEST_FILE_NAME),
    ],
    {
      env: buildPythonProcessEnvironment({ pythonEnvironmentPath }),
      timeout: 15_000,
      maxBuffer: 64 * 1024,
      windowsHide: true,
    },
  );
}
