// FileName: projectManifest.ts

import type {
  Str_ProjectType,
  DictProjectManifest_Flow,
  DictProjectManifest_Component,
  DictProjectManifest,
} from "./projectTypes";
import { isRecord, isStringRecord, hasExactKeys } from "../../Common/typeCheck";
import { readJsonFile, writeJsonFile } from "../../Common/utils";

const SET_KEYS_FLOW_MANIFEST = new Set([
  "schemaVersion",
  "name",
  "version",
  "description",
  "requiresLiberrpa",
  "componentDependencies",
]);

const SET_KEYS_COMPONENT_MANIFEST = new Set([
  "schemaVersion",
  "id",
  "packageName",
  "displayName",
  "version",
  "description",
  "requiresLiberrpa",
  "componentDependencies",
]);

export function parseFlowManifest(
  value: unknown,
  sourceName: string,
): DictProjectManifest_Flow {
  if (
    isRecord(value) &&
    hasExactKeys(value, SET_KEYS_FLOW_MANIFEST) &&
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

  throw new Error(`Invalid Flow Project manifest: ${sourceName}`);
}

export function parseComponentManifest(
  value: unknown,
  sourceName: string,
): DictProjectManifest_Component {
  if (
    isRecord(value) &&
    hasExactKeys(value, SET_KEYS_COMPONENT_MANIFEST) &&
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

  throw new Error(`Invalid Component Project manifest: ${sourceName}`);
}

export function parseProjectManifest(
  value: unknown,
  projectType: Str_ProjectType,
  sourceName: string,
): DictProjectManifest {
  return projectType === "flow"
    ? parseFlowManifest(value, sourceName)
    : parseComponentManifest(value, sourceName);
}

export function readFlowManifest(manifestFilePath: string): DictProjectManifest_Flow {
  return parseFlowManifest(readJsonFile(manifestFilePath), manifestFilePath);
}

export function readComponentManifest(
  manifestFilePath: string,
): DictProjectManifest_Component {
  return parseComponentManifest(readJsonFile(manifestFilePath), manifestFilePath);
}

export function writeFlowManifest(
  manifestFilePath: string,
  manifest: DictProjectManifest_Flow,
): void {
  writeJsonFile(manifestFilePath, manifest);
}

export function writeComponentManifest(
  manifestFilePath: string,
  manifest: DictProjectManifest_Component,
): void {
  writeJsonFile(manifestFilePath, manifest);
}
