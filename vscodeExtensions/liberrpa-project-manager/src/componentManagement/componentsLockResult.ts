// FileName: componentsLockResult.ts

import { ensureExactRecord, ensureString, isRecord, isStringRecord } from "../typeCheck";
import type {
  DictComponentsLock_Root,
  DictComponentsLock_Component,
  DictComponentsLock_File,
} from "./protocol";

const SET_COMPONENTS_LOCK_FILE_KEYS = new Set(["schemaVersion", "root", "components"]);
const SET_COMPONENTS_LOCK_ROOT_FLOW_KEYS = new Set([
  "manifestFile",
  "manifestSchemaVersion",
  "requiresLiberrpa",
  "componentDependencies",
  "resolutionInputSha256",
]);
const SET_COMPONENTS_LOCK_ROOT_COMPONENT_KEYS = new Set([
  "manifestFile",
  "manifestSchemaVersion",
  "componentId",
  "packageName",
  "requiresLiberrpa",
  "componentDependencies",
  "resolutionInputSha256",
]);
const SET_COMPONENTS_LOCK_COMPONENT_KEYS = new Set([
  "manifestSchemaVersion",
  "packageName",
  "displayName",
  "version",
  "wheelFile",
  "sha256",
  "requiresLiberrpa",
  "componentDependencies",
]);

function parseComponentsLockRoot(
  value: unknown,
  sourceName: string,
): DictComponentsLock_Root {
  if (!isRecord(value)) {
    throw new Error(`${sourceName} must be an object.`);
  }

  const strManifestFile = value["manifestFile"];
  if (strManifestFile === "flow.json") {
    const dictValue = ensureExactRecord(
      value,
      SET_COMPONENTS_LOCK_ROOT_FLOW_KEYS,
      sourceName,
    );
    if (
      dictValue["manifestSchemaVersion"] !== 1 ||
      !isStringRecord(dictValue["componentDependencies"])
    ) {
      throw new Error(`${sourceName} is invalid.`);
    }

    return {
      manifestFile: "flow.json",
      manifestSchemaVersion: 1,
      requiresLiberrpa: ensureString(
        dictValue["requiresLiberrpa"],
        `${sourceName}.requiresLiberrpa`,
      ),
      componentDependencies: dictValue["componentDependencies"],
      resolutionInputSha256: ensureString(
        dictValue["resolutionInputSha256"],
        `${sourceName}.resolutionInputSha256`,
      ),
    };
  }

  if (strManifestFile === "component.json") {
    const dictValue = ensureExactRecord(
      value,
      SET_COMPONENTS_LOCK_ROOT_COMPONENT_KEYS,
      sourceName,
    );
    if (
      dictValue["manifestSchemaVersion"] !== 1 ||
      !isStringRecord(dictValue["componentDependencies"])
    ) {
      throw new Error(`${sourceName} is invalid.`);
    }

    return {
      manifestFile: "component.json",
      manifestSchemaVersion: 1,
      componentId: ensureString(dictValue["componentId"], `${sourceName}.componentId`),
      packageName: ensureString(dictValue["packageName"], `${sourceName}.packageName`),
      requiresLiberrpa: ensureString(
        dictValue["requiresLiberrpa"],
        `${sourceName}.requiresLiberrpa`,
      ),
      componentDependencies: dictValue["componentDependencies"],
      resolutionInputSha256: ensureString(
        dictValue["resolutionInputSha256"],
        `${sourceName}.resolutionInputSha256`,
      ),
    };
  }

  throw new Error(`${sourceName}.manifestFile is invalid.`);
}

function parseComponentsLockComponent(
  value: unknown,
  sourceName: string,
): DictComponentsLock_Component {
  const dictValue = ensureExactRecord(
    value,
    SET_COMPONENTS_LOCK_COMPONENT_KEYS,
    sourceName,
  );
  if (
    dictValue["manifestSchemaVersion"] !== 1 ||
    !isStringRecord(dictValue["componentDependencies"])
  ) {
    throw new Error(`${sourceName} is invalid.`);
  }

  return {
    manifestSchemaVersion: 1,
    packageName: ensureString(dictValue["packageName"], `${sourceName}.packageName`),
    displayName: ensureString(dictValue["displayName"], `${sourceName}.displayName`),
    version: ensureString(dictValue["version"], `${sourceName}.version`),
    wheelFile: ensureString(dictValue["wheelFile"], `${sourceName}.wheelFile`),
    sha256: ensureString(dictValue["sha256"], `${sourceName}.sha256`),
    requiresLiberrpa: ensureString(
      dictValue["requiresLiberrpa"],
      `${sourceName}.requiresLiberrpa`,
    ),
    componentDependencies: dictValue["componentDependencies"],
  };
}

export function parseComponentsLock(
  value: unknown,
  sourceName: string,
): DictComponentsLock_File {
  const dictValue = ensureExactRecord(value, SET_COMPONENTS_LOCK_FILE_KEYS, sourceName);
  if (dictValue["schemaVersion"] !== 1 || !isRecord(dictValue["components"])) {
    throw new Error(`${sourceName} is invalid.`);
  }

  const components: Record<string, DictComponentsLock_Component> = {};
  for (const [strComponentId, componentValue] of Object.entries(dictValue["components"])) {
    components[strComponentId] = parseComponentsLockComponent(
      componentValue,
      `${sourceName}.components.${strComponentId}`,
    );
  }

  return {
    schemaVersion: 1,
    root: parseComponentsLockRoot(dictValue["root"], `${sourceName}.root`),
    components,
  };
}

export function parseOptionalComponentsLock(
  value: unknown,
  sourceName: string,
): DictComponentsLock_File | null {
  return value === null ? null : parseComponentsLock(value, sourceName);
}
