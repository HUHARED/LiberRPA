// FileName: projectManifest.ts

import * as fs from "node:fs";
import * as path from "node:path";
import { randomUUID } from "node:crypto";

import { isRecord, isStringRecord, hasExactKeys } from "./typeCheck";
import type { ProjectType } from "./webviewMessages";
import { getComponentPackageNameError, getDisplayNameError } from "./projectValidation";
import { readJsonFile, writeJsonFile } from "./utils";

const SET_FLOW_MANIFEST_KEYS = new Set([
  "schemaVersion",
  "name",
  "version",
  "description",
  "requiresLiberrpa",
  "componentDependencies",
]);

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

export interface ProjectManifestDefaults {
  version: string;
  description: string;
}

export function getProjectManifestDefaults(
  templatePath: string,
  projectType: ProjectType,
): ProjectManifestDefaults {
  switch (projectType) {
    case "flow": {
      const manifest = readFlowManifest(path.join(templatePath, "flow.json"));
      return {
        version: manifest.version,
        description: manifest.description,
      };
    }

    case "component": {
      const manifest = readComponentManifest(path.join(templatePath, "component.json"));
      return {
        version: manifest.version,
        description: manifest.description,
      };
    }
  }
}

export function initializeFlowProject(
  projectPath: string,
  projectName: string,
  version: string,
  description: string,
): void {
  const normalizedProjectName = projectName.trim();
  if (normalizedProjectName.length === 0) {
    throw new Error("Flow Project name cannot be empty.");
  }

  const manifestPath = path.join(projectPath, "flow.json");
  const manifest = readFlowManifest(manifestPath);
  manifest.name = normalizedProjectName;
  manifest.version = version;
  manifest.description = description;
  writeJsonFile(manifestPath, manifest);
}

export function initializeComponentProject(
  projectPath: string,
  packageName: string,
  displayName: string,
  version: string,
  description: string,
): void {
  const packageNameError = getComponentPackageNameError(packageName);
  if (packageNameError !== undefined) {
    throw new Error(packageNameError);
  }

  const displayNameError = getDisplayNameError(displayName);
  if (displayNameError !== undefined) {
    throw new Error(displayNameError);
  }

  const manifestPath = path.join(projectPath, "component.json");
  const manifest = readComponentManifest(manifestPath);
  manifest.id = randomUUID();
  manifest.packageName = packageName;
  manifest.displayName = displayName.trim();
  manifest.version = version;
  manifest.description = description;
  writeJsonFile(manifestPath, manifest);

  const packagePath = path.join(projectPath, "src", packageName);

  fs.mkdirSync(packagePath, { recursive: true });

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
    hasExactKeys(value, SET_FLOW_MANIFEST_KEYS) &&
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
    hasExactKeys(value, SET_COMPONENT_MANIFEST_KEYS) &&
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
