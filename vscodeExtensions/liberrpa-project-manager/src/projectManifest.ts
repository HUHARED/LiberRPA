// FileName: projectManifest.ts

import * as fs from "node:fs";
import * as path from "node:path";
import { randomUUID } from "node:crypto";

import { isRecord, stringifyJson } from "./commonFunc";

export const COMPONENT_PACKAGE_NAME_PATTERN = /^[A-Z][A-Za-z0-9]*$/;

const SET_INVALID_PYTHON_IDENTIFIERS = new Set(["False", "None", "True"]);
const SET_RESERVED_WINDOWS_NAMES = new Set([
  "CON",
  "PRN",
  "AUX",
  "NUL",
  "COM1",
  "COM2",
  "COM3",
  "COM4",
  "COM5",
  "COM6",
  "COM7",
  "COM8",
  "COM9",
  "LPT1",
  "LPT2",
  "LPT3",
  "LPT4",
  "LPT5",
  "LPT6",
  "LPT7",
  "LPT8",
  "LPT9",
]);

const FLOW_MANIFEST_KEYS = new Set([
  "schemaVersion",
  "name",
  "version",
  "description",
  "requiresLiberrpa",
  "componentDependencies",
]);

const COMPONENT_MANIFEST_KEYS = new Set([
  "schemaVersion",
  "id",
  "packageName",
  "displayName",
  "version",
  "description",
  "requiresLiberrpa",
  "componentDependencies",
]);

interface FlowManifestV1 {
  schemaVersion: 1;
  name: string;
  version: string;
  description: string;
  requiresLiberrpa: string;
  componentDependencies: Record<string, string>;
}

interface ComponentManifestV1 {
  schemaVersion: 1;
  id: string;
  packageName: string;
  displayName: string;
  version: string;
  description: string;
  requiresLiberrpa: string;
  componentDependencies: Record<string, string>;
}

export function getComponentPackageNameError(packageName: string): string | undefined {
  if (!COMPONENT_PACKAGE_NAME_PATTERN.test(packageName)) {
    return "Package name must use PascalCase and contain only ASCII letters and digits, for example: ExcelTools.";
  }

  if (SET_INVALID_PYTHON_IDENTIFIERS.has(packageName)) {
    return `Package name cannot be the Python keyword "${packageName}".`;
  }

  if (packageName.toLowerCase() === "liberrpa") {
    return 'Package name "Liberrpa" is reserved by LiberRPA.';
  }

  if (SET_RESERVED_WINDOWS_NAMES.has(packageName.toUpperCase())) {
    return `Package name "${packageName}" is reserved by Windows.`;
  }

  return undefined;
}

export function initializeFlowProject(projectPath: string, projectName: string): void {
  const normalizedProjectName = projectName.trim();
  if (normalizedProjectName.length === 0) {
    throw new Error("Flow Project name cannot be empty.");
  }

  const manifestPath = path.join(projectPath, "flow.json");
  const manifest = readFlowManifest(manifestPath);
  manifest.name = normalizedProjectName;
  writeJsonFile(manifestPath, manifest);
}

export function initializeComponentProject(
  projectPath: string,
  packageName: string,
  displayName: string,
): void {
  const packageNameError = getComponentPackageNameError(packageName);
  if (packageNameError !== undefined) {
    throw new Error(packageNameError);
  }

  const normalizedDisplayName = displayName.trim();
  if (normalizedDisplayName.length === 0) {
    throw new Error("Component display name cannot be empty.");
  }

  const manifestPath = path.join(projectPath, "component.json");
  const manifest = readComponentManifest(manifestPath);
  manifest.id = randomUUID();
  manifest.packageName = packageName;
  manifest.displayName = normalizedDisplayName;
  writeJsonFile(manifestPath, manifest);

  const sourcePath = path.join(projectPath, "src");
  const packagePath = path.join(sourcePath, packageName);

  fs.mkdirSync(sourcePath, { recursive: true });
  fs.mkdirSync(packagePath);
  fs.writeFileSync(path.join(packagePath, "__init__.py"), "", {
    encoding: "utf-8",
    flag: "wx",
  });
  fs.writeFileSync(path.join(packagePath, "py.typed"), "", {
    encoding: "utf-8",
    flag: "wx",
  });
}

function readFlowManifest(manifestPath: string): FlowManifestV1 {
  const value = readJsonFile(manifestPath);

  if (
    isRecord(value) &&
    hasExactKeys(value, FLOW_MANIFEST_KEYS) &&
    value["schemaVersion"] === 1 &&
    typeof value["name"] === "string" &&
    typeof value["version"] === "string" &&
    typeof value["description"] === "string" &&
    typeof value["requiresLiberrpa"] === "string" &&
    isStringRecord(value["componentDependencies"])
  ) {
    return {
      schemaVersion: 1,
      name: value["name"],
      version: value["version"],
      description: value["description"],
      requiresLiberrpa: value["requiresLiberrpa"],
      componentDependencies: value["componentDependencies"],
    };
  }

  throw new Error(`Invalid Flow Project manifest: ${manifestPath}`);
}

function readComponentManifest(manifestPath: string): ComponentManifestV1 {
  const value = readJsonFile(manifestPath);

  if (
    isRecord(value) &&
    hasExactKeys(value, COMPONENT_MANIFEST_KEYS) &&
    value["schemaVersion"] === 1 &&
    typeof value["id"] === "string" &&
    typeof value["packageName"] === "string" &&
    typeof value["displayName"] === "string" &&
    typeof value["version"] === "string" &&
    typeof value["description"] === "string" &&
    typeof value["requiresLiberrpa"] === "string" &&
    isStringRecord(value["componentDependencies"])
  ) {
    return {
      schemaVersion: 1,
      id: value["id"],
      packageName: value["packageName"],
      displayName: value["displayName"],
      version: value["version"],
      description: value["description"],
      requiresLiberrpa: value["requiresLiberrpa"],
      componentDependencies: value["componentDependencies"],
    };
  }

  throw new Error(`Invalid Component Project manifest: ${manifestPath}`);
}

function readJsonFile(filePath: string): unknown {
  const content = fs.readFileSync(filePath, { encoding: "utf-8" });
  return JSON.parse(content) as unknown;
}

function writeJsonFile(filePath: string, value: object): void {
  fs.writeFileSync(filePath, stringifyJson(value, 2), { encoding: "utf-8" });
}

function hasExactKeys(
  value: Record<string, unknown>,
  expectedKeys: ReadonlySet<string>,
): boolean {
  const keys = Object.keys(value);
  return keys.length === expectedKeys.size && keys.every((key) => expectedKeys.has(key));
}

function isStringRecord(value: unknown): value is Record<string, string> {
  return isRecord(value) && Object.values(value).every((item) => typeof item === "string");
}
