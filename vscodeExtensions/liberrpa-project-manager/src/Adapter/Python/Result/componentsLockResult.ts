// FileName: componentsLockResult.ts

import {
  isRecord,
  isStringRecord,
  ensureExactRecord,
  ensureString,
  ensureSha256,
} from "../../../Common/typeCheck";
import type {
  DictComponentsLock_Root,
  DictComponentsLock_Component,
  DictComponentsLock_File,
} from "../../../Domain/ComponentManagement/componentManagementTypes";

const SET_KEYS_COMPONENTS_LOCK_FILE = new Set(["schemaVersion", "root", "components"]);
const SET_KEYS_COMPONENTS_LOCK_ROOT_FLOW = new Set([
  "manifestFileName",
  "requiresLiberrpa",
  "componentDependencies",
]);
const SET_KEYS_COMPONENTS_LOCK_ROOT_COMPONENT = new Set([
  "manifestFileName",
  "componentId",
  "packageName",
  "requiresLiberrpa",
  "componentDependencies",
]);
const SET_KEYS_COMPONENTS_LOCK_COMPONENT = new Set([
  "packageName",
  "displayName",
  "version",
  "wheelFileName",
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

  const strManifestFileName = value["manifestFileName"];
  if (strManifestFileName === "flow.json") {
    const dictValue = ensureExactRecord(
      value,
      SET_KEYS_COMPONENTS_LOCK_ROOT_FLOW,
      sourceName,
    );
    if (!isStringRecord(dictValue["componentDependencies"])) {
      throw new Error(`${sourceName}.componentDependencies is invalid.`);
    }

    return {
      manifestFileName: "flow.json",
      requiresLiberrpa: ensureString(
        dictValue["requiresLiberrpa"],
        `${sourceName}.requiresLiberrpa`,
      ),
      componentDependencies: dictValue["componentDependencies"],
    };
  }

  if (strManifestFileName === "component.json") {
    const dictValue = ensureExactRecord(
      value,
      SET_KEYS_COMPONENTS_LOCK_ROOT_COMPONENT,
      sourceName,
    );
    if (!isStringRecord(dictValue["componentDependencies"])) {
      throw new Error(`${sourceName}.componentDependencies is invalid.`);
    }

    return {
      manifestFileName: "component.json",
      componentId: ensureString(dictValue["componentId"], `${sourceName}.componentId`),
      packageName: ensureString(dictValue["packageName"], `${sourceName}.packageName`),
      requiresLiberrpa: ensureString(
        dictValue["requiresLiberrpa"],
        `${sourceName}.requiresLiberrpa`,
      ),
      componentDependencies: dictValue["componentDependencies"],
    };
  }

  throw new Error(`${sourceName}.manifestFileName is invalid.`);
}

function parseComponentsLockComponent(
  value: unknown,
  sourceName: string,
): DictComponentsLock_Component {
  const dictValue = ensureExactRecord(
    value,
    SET_KEYS_COMPONENTS_LOCK_COMPONENT,
    sourceName,
  );
  if (!isStringRecord(dictValue["componentDependencies"])) {
    throw new Error(`${sourceName}.componentDependencies is invalid.`);
  }

  return {
    packageName: ensureString(dictValue["packageName"], `${sourceName}.packageName`),
    displayName: ensureString(dictValue["displayName"], `${sourceName}.displayName`),
    version: ensureString(dictValue["version"], `${sourceName}.version`),
    wheelFileName: ensureString(dictValue["wheelFileName"], `${sourceName}.wheelFileName`),
    sha256: ensureSha256(dictValue["sha256"], `${sourceName}.sha256`),
    requiresLiberrpa: ensureString(
      dictValue["requiresLiberrpa"],
      `${sourceName}.requiresLiberrpa`,
    ),
    componentDependencies: dictValue["componentDependencies"],
  };
}

function parseComponentsLock(value: unknown, sourceName: string): DictComponentsLock_File {
  const dictValue = ensureExactRecord(value, SET_KEYS_COMPONENTS_LOCK_FILE, sourceName);
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
