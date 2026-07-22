// FileName: projectManifest.ts

import * as fs from "node:fs";
import * as path from "node:path";
import { randomUUID } from "node:crypto";

import type { ProjectType } from "./webviewMessages";
import { isRecord, isStringRecord, hasExactKeys } from "./typeCheck";
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

interface DictFlowManifestV1 {
  schemaVersion: 1;
  name: string;
  version: string;
  description: string;
  requiresLiberrpa: string;
  componentDependencies: Record<string, string>;
}

interface DictComponentManifestV1 {
  schemaVersion: 1;
  id: string;
  packageName: string;
  displayName: string;
  version: string;
  description: string;
  requiresLiberrpa: string;
  componentDependencies: Record<string, string>;
}

interface DictProjectManifestDefaultInfo {
  defaultVersion: string;
  defaultDescription: string;
}

function readFlowManifest(manifestPath: string): DictFlowManifestV1 {
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

function readComponentManifest(manifestPath: string): DictComponentManifestV1 {
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

export function getProjectManifestDefaults(
  templatePath: string,
  projectType: ProjectType,
): DictProjectManifestDefaultInfo {
  switch (projectType) {
    case "flow": {
      const dictManifest = readFlowManifest(path.join(templatePath, "flow.json"));
      return {
        defaultVersion: dictManifest.version,
        defaultDescription: dictManifest.description,
      };
    }

    case "component": {
      const dictManifest = readComponentManifest(path.join(templatePath, "component.json"));
      return {
        defaultVersion: dictManifest.version,
        defaultDescription: dictManifest.description,
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
  const strManifestPath = path.join(projectPath, "flow.json");
  const dictManifest = readFlowManifest(strManifestPath);
  dictManifest.name = projectName;
  dictManifest.version = version;
  dictManifest.description = description;
  writeJsonFile(strManifestPath, dictManifest);
}

export function initializeComponentProject(
  projectPath: string,
  packageName: string,
  displayName: string,
  version: string,
  description: string,
): void {
  const strManifestPath = path.join(projectPath, "component.json");
  const dictManifest = readComponentManifest(strManifestPath);
  dictManifest.id = randomUUID();
  dictManifest.packageName = packageName;
  dictManifest.displayName = displayName;
  dictManifest.version = version;
  dictManifest.description = description;
  writeJsonFile(strManifestPath, dictManifest);

  // The "src" folder needs packageName.
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
