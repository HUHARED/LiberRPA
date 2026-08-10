// FileName: repositoryResult.ts

import {
  isStringRecord,
  ensureExactRecord,
  ensureString,
  ensureNonEmptyString,
  ensureSha256,
  ensureNonNegativeInteger,
} from "../../../Common/typeCheck";
import type {
  DictProtocolResult_ComponentWheelsImported_Component,
  DictProtocolResult_ComponentWheelsImported,
  DictProtocolResult_RepositoryIndexRebuilt,
  DictRepository_ComponentVersionEntry,
  DictProtocolResult_RepositoryCatalog_Component,
  DictProtocolResult_RepositoryCatalog,
} from "../../../Domain/ComponentManagement/componentManagementTypes";

const SET_KEYS_REPOSITORY_INDEX_REBUILT = new Set([
  "status",
  "componentCount",
  "versionCount",
]);
const SET_KEYS_COMPONENT_WHEELS_IMPORTED_RESULT = new Set([
  "status",
  "importedCount",
  "alreadyImportedCount",
  "components",
]);
const SET_KEYS_COMPONENT_WHEELS_IMPORTED_COMPONENT = new Set([
  "sourceWheelFilePath",
  "componentId",
  "packageName",
  "version",
  "wheelFileName",
  "sha256",
  "status",
]);
const SET_KEYS_REPOSITORY_CATALOG_RESULT = new Set([
  "status",
  "repositoryPath",
  "componentCount",
  "versionCount",
  "components",
]);
const SET_KEYS_REPOSITORY_CATALOG_COMPONENT = new Set([
  "componentId",
  "packageName",
  "versions",
]);
const SET_KEYS_REPOSITORY_COMPONENT_VERSION = new Set([
  "version",
  "displayName",
  "description",
  "requiresLiberrpa",
  "componentDependencies",
  "wheelFileName",
  "sha256",
]);

export function parseRepositoryIndexRebuiltResult(
  value: unknown,
): DictProtocolResult_RepositoryIndexRebuilt {
  const dictValue = ensureExactRecord(
    value,
    SET_KEYS_REPOSITORY_INDEX_REBUILT,
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

function parseImportedComponent(
  value: unknown,
  sourceName: string,
): DictProtocolResult_ComponentWheelsImported_Component {
  const dictValue = ensureExactRecord(
    value,
    SET_KEYS_COMPONENT_WHEELS_IMPORTED_COMPONENT,
    sourceName,
  );
  const status = dictValue["status"];
  if (status !== "imported" && status !== "alreadyImported") {
    throw new Error(`${sourceName}.status is unsupported.`);
  }

  return {
    sourceWheelFilePath: ensureNonEmptyString(
      dictValue["sourceWheelFilePath"],
      `${sourceName}.sourceWheelFilePath`,
    ),
    componentId: ensureNonEmptyString(
      dictValue["componentId"],
      `${sourceName}.componentId`,
    ),
    packageName: ensureNonEmptyString(
      dictValue["packageName"],
      `${sourceName}.packageName`,
    ),
    version: ensureNonEmptyString(dictValue["version"], `${sourceName}.version`),
    wheelFileName: ensureNonEmptyString(
      dictValue["wheelFileName"],
      `${sourceName}.wheelFileName`,
    ),
    sha256: ensureSha256(dictValue["sha256"], `${sourceName}.sha256`),
    status,
  };
}

export function parseComponentWheelsImportedResult(
  value: unknown,
): DictProtocolResult_ComponentWheelsImported {
  const dictValue = ensureExactRecord(
    value,
    SET_KEYS_COMPONENT_WHEELS_IMPORTED_RESULT,
    "Import Component Wheels result",
  );
  if (dictValue["status"] !== "componentWheelsImported") {
    throw new Error("Component Management returned an unsupported Wheel import status.");
  }

  const arrComponent = dictValue["components"];
  if (!Array.isArray(arrComponent) || arrComponent.length === 0) {
    throw new Error("Import Component Wheels result.components must be a non-empty array.");
  }

  const components = arrComponent.map((item, intIndex) =>
    parseImportedComponent(item, `components[${String(intIndex)}]`),
  );
  const importedCount = ensureNonNegativeInteger(
    dictValue["importedCount"],
    "Import Component Wheels result.importedCount",
  );
  const alreadyImportedCount = ensureNonNegativeInteger(
    dictValue["alreadyImportedCount"],
    "Import Component Wheels result.alreadyImportedCount",
  );

  if (
    importedCount !==
      components.filter((component) => component.status === "imported").length ||
    alreadyImportedCount !==
      components.filter((component) => component.status === "alreadyImported").length
  ) {
    throw new Error("Import Component Wheels result counts do not match components.");
  }

  return {
    status: "componentWheelsImported",
    importedCount,
    alreadyImportedCount,
    components,
  };
}

function parseRepositoryComponentVersion(
  value: unknown,
  sourceName: string,
): DictRepository_ComponentVersionEntry {
  const dictValue = ensureExactRecord(
    value,
    SET_KEYS_REPOSITORY_COMPONENT_VERSION,
    sourceName,
  );
  if (!isStringRecord(dictValue["componentDependencies"])) {
    throw new Error(`${sourceName}.componentDependencies must be a string object.`);
  }

  return {
    version: ensureString(dictValue["version"], `${sourceName}.version`),
    displayName: ensureString(dictValue["displayName"], `${sourceName}.displayName`),
    description: ensureString(dictValue["description"], `${sourceName}.description`),
    requiresLiberrpa: ensureString(
      dictValue["requiresLiberrpa"],
      `${sourceName}.requiresLiberrpa`,
    ),
    componentDependencies: dictValue["componentDependencies"],
    wheelFileName: ensureString(dictValue["wheelFileName"], `${sourceName}.wheelFileName`),
    sha256: ensureSha256(dictValue["sha256"], `${sourceName}.sha256`),
  };
}

function parseRepositoryCatalogComponent(
  value: unknown,
  sourceName: string,
): DictProtocolResult_RepositoryCatalog_Component {
  const dictValue = ensureExactRecord(
    value,
    SET_KEYS_REPOSITORY_CATALOG_COMPONENT,
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
    SET_KEYS_REPOSITORY_CATALOG_RESULT,
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
