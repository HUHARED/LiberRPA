// FileName: componentManagementRepositoryResult.ts

import {
  ensureExactRecord,
  ensureNonNegativeInteger,
  ensureString,
  isStringRecord,
} from "../typeCheck";
import type {
  DictProtocolResult_RepositoryIndexRebuilt,
  DictRepository_ComponentVersion,
  DictProtocolResult_RepositoryCatalog_Component,
  DictProtocolResult_RepositoryCatalog,
} from "./protocol";

const SET_REPOSITORY_INDEX_REBUILT_KEYS = new Set([
  "status",
  "componentCount",
  "versionCount",
]);
const SET_REPOSITORY_CATALOG_RESULT_KEYS = new Set([
  "status",
  "repositoryPath",
  "componentCount",
  "versionCount",
  "components",
]);
const SET_REPOSITORY_CATALOG_COMPONENT_KEYS = new Set([
  "componentId",
  "packageName",
  "versions",
]);
const SET_REPOSITORY_COMPONENT_VERSION_KEYS = new Set([
  "version",
  "displayName",
  "description",
  "manifestSchemaVersion",
  "wheelFile",
  "sha256",
  "requiresLiberrpa",
  "componentDependencies",
]);

export function parseRepositoryIndexRebuiltResult(
  value: unknown,
): DictProtocolResult_RepositoryIndexRebuilt {
  const dictValue = ensureExactRecord(
    value,
    SET_REPOSITORY_INDEX_REBUILT_KEYS,
    "Repository index rebuilt result",
  );
  if (dictValue["status"] !== "repositoryIndexRebuilt") {
    throw new Error(
      "Component Management returned an unsupported Repository rebuild status.",
    );
  }

  return {
    status: "repositoryIndexRebuilt",
    componentCount: ensureNonNegativeInteger(
      dictValue["componentCount"],
      "Repository index rebuilt result.componentCount",
    ),
    versionCount: ensureNonNegativeInteger(
      dictValue["versionCount"],
      "Repository index rebuilt result.versionCount",
    ),
  };
}

function parseRepositoryComponentVersion(
  value: unknown,
  sourceName: string,
): DictRepository_ComponentVersion {
  const dictValue = ensureExactRecord(
    value,
    SET_REPOSITORY_COMPONENT_VERSION_KEYS,
    sourceName,
  );

  if (dictValue["manifestSchemaVersion"] !== 1) {
    throw new Error(`${sourceName}.manifestSchemaVersion must be 1.`);
  }
  if (!isStringRecord(dictValue["componentDependencies"])) {
    throw new Error(`${sourceName}.componentDependencies must be a string object.`);
  }

  return {
    version: ensureString(dictValue["version"], `${sourceName}.version`),
    displayName: ensureString(dictValue["displayName"], `${sourceName}.displayName`),
    description: ensureString(dictValue["description"], `${sourceName}.description`),
    manifestSchemaVersion: 1,
    wheelFile: ensureString(dictValue["wheelFile"], `${sourceName}.wheelFile`),
    sha256: ensureString(dictValue["sha256"], `${sourceName}.sha256`),
    requiresLiberrpa: ensureString(
      dictValue["requiresLiberrpa"],
      `${sourceName}.requiresLiberrpa`,
    ),
    componentDependencies: dictValue["componentDependencies"],
  };
}

function parseRepositoryCatalogComponent(
  value: unknown,
  sourceName: string,
): DictProtocolResult_RepositoryCatalog_Component {
  const dictValue = ensureExactRecord(
    value,
    SET_REPOSITORY_CATALOG_COMPONENT_KEYS,
    sourceName,
  );
  const arrVersion = dictValue["versions"];
  if (!Array.isArray(arrVersion) || arrVersion.length === 0) {
    throw new Error(`${sourceName}.versions must be a non-empty array.`);
  }

  return {
    componentId: ensureString(dictValue["componentId"], `${sourceName}.componentId`),
    packageName: ensureString(dictValue["packageName"], `${sourceName}.packageName`),
    versions: arrVersion.map((item, intIndex) =>
      parseRepositoryComponentVersion(item, `${sourceName}.versions[${String(intIndex)}]`),
    ),
  };
}

export function parseRepositoryCatalogResult(
  value: unknown,
): DictProtocolResult_RepositoryCatalog {
  const dictValue = ensureExactRecord(
    value,
    SET_REPOSITORY_CATALOG_RESULT_KEYS,
    "Component Repository catalog result",
  );
  if (dictValue["status"] !== "componentRepositoryCatalog") {
    throw new Error(
      "Component Management returned an unsupported Repository catalog status.",
    );
  }

  const arrComponent = dictValue["components"];
  if (!Array.isArray(arrComponent)) {
    throw new Error("Component Repository catalog components must be an array.");
  }

  const components = arrComponent.map((item, intIndex) =>
    parseRepositoryCatalogComponent(item, `components[${String(intIndex)}]`),
  );
  const componentCount = ensureNonNegativeInteger(
    dictValue["componentCount"],
    "Component Repository catalog componentCount",
  );
  const versionCount = ensureNonNegativeInteger(
    dictValue["versionCount"],
    "Component Repository catalog versionCount",
  );

  if (componentCount !== components.length) {
    throw new Error(
      "Component Repository catalog componentCount does not match components.",
    );
  }
  if (
    versionCount !==
    components.reduce((intTotal, component) => intTotal + component.versions.length, 0)
  ) {
    throw new Error("Component Repository catalog versionCount does not match components.");
  }

  return {
    status: "componentRepositoryCatalog",
    repositoryPath: ensureString(
      dictValue["repositoryPath"],
      "Component Repository catalog repositoryPath",
    ),
    componentCount,
    versionCount,
    components,
  };
}
