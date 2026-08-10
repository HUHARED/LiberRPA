// FileName: projectDependencyResult.ts

import {
  isRecord,
  ensureExactRecord,
  ensureString,
  ensureSha256,
  ensureNonNegativeInteger,
} from "../../../Common/typeCheck";
import type {
  Str_ProjectDependency_LockState,
  Str_ProjectDependency_ComponentsState,
  Str_ProjectDependency_EnvironmentState,
  Str_ProjectDependency_RepairState,
  DictProjectDependency_DirectChange,
  DictProjectDependency_ResolvedChange,
  DictProtocolResult_ComponentsFolder,
  DictProtocolResult_ProjectDependencyState,
  DictProtocolResult_ProjectDependencyPlan,
  DictProtocolResult_ProjectDependencyPlanApplied,
  DictProtocolResult_ProjectComponentsRepaired,
} from "../../../Domain/ComponentManagement/componentManagementTypes";
import type { Str_ProjectType } from "../../../Domain/Project/projectTypes";
import { parseOptionalComponentsLock } from "./componentsLockResult";
import { parseProjectManifest } from "../../../Domain/Project/projectManifest";

const SET_KEYS_PROJECT_DEPENDENCY_STATE = new Set([
  "status",
  "projectPath",
  "projectType",
  "manifest",
  "componentsLock",
  "lockState",
  "componentsState",
  "environmentState",
  "repairState",
  "details",
]);
const SET_KEYS_PROJECT_DEPENDENCY_PLAN = new Set([
  "status",
  "planSha256",
  "sourceManifest",
  "sourceComponentsLock",
  "targetManifest",
  "targetComponentsLock",
  "directDependencyChanges",
  "resolvedComponentChanges",
]);
const SET_KEYS_PROJECT_DEPENDENCY_PLAN_APPLIED = new Set([
  "status",
  "planSha256",
  "targetManifest",
  "targetComponentsLock",
  "directDependencyChanges",
  "resolvedComponentChanges",
  "componentsFolder",
]);
const SET_KEYS_PROJECT_COMPONENTS_FOLDER = new Set([
  "componentsFolderPath",
  "componentCount",
  "fileCount",
]);
const SET_KEYS_PROJECT_COMPONENTS_REPAIRED = new Set(["status", "componentsFolder"]);

function parseProjectType(value: unknown, sourceName: string): Str_ProjectType {
  if (value !== "flow" && value !== "component") {
    throw new Error(`${sourceName} must be "flow" or "component".`);
  }
  return value;
}

function parseLockState(value: unknown): Str_ProjectDependency_LockState {
  if (
    value !== "notRequired" &&
    value !== "missing" &&
    value !== "invalid" &&
    value !== "stale" &&
    value !== "valid"
  ) {
    throw new Error("Project dependency lockState is invalid.");
  }
  return value;
}

function parseComponentsState(value: unknown): Str_ProjectDependency_ComponentsState {
  if (
    value !== "notRequired" &&
    value !== "unverified" &&
    value !== "missing" &&
    value !== "damaged" &&
    value !== "valid"
  ) {
    throw new Error("Project dependency componentsState is invalid.");
  }
  return value;
}

function parseEnvironmentState(value: unknown): Str_ProjectDependency_EnvironmentState {
  if (value !== "unknown" && value !== "compatible" && value !== "incompatible") {
    throw new Error("Project dependency environmentState is invalid.");
  }
  return value;
}

function parseRepairState(value: unknown): Str_ProjectDependency_RepairState {
  if (
    value !== "notApplicable" &&
    value !== "available" &&
    value !== "repositoryUnavailable" &&
    value !== "wheelMissing" &&
    value !== "wheelHashMismatch"
  ) {
    throw new Error("Project dependency repairState is invalid.");
  }
  return value;
}

export function parseProjectDependencyStateResult(
  value: unknown,
): DictProtocolResult_ProjectDependencyState {
  const dictValue = ensureExactRecord(
    value,
    SET_KEYS_PROJECT_DEPENDENCY_STATE,
    "Project dependency state result",
  );
  if (dictValue["status"] !== "projectDependencyState" || !isRecord(dictValue["details"])) {
    throw new Error("Component Management returned an invalid Project dependency state.");
  }

  const projectType = parseProjectType(
    dictValue["projectType"],
    "Project dependency state projectType",
  );

  return {
    status: "projectDependencyState",
    projectPath: ensureString(
      dictValue["projectPath"],
      "Project dependency state projectPath",
    ),
    projectType,
    manifest: parseProjectManifest(
      dictValue["manifest"],
      projectType,
      "Project dependency state manifest",
    ),
    componentsLock: parseOptionalComponentsLock(
      dictValue["componentsLock"],
      "Project dependency state componentsLock",
    ),
    lockState: parseLockState(dictValue["lockState"]),
    componentsState: parseComponentsState(dictValue["componentsState"]),
    environmentState: parseEnvironmentState(dictValue["environmentState"]),
    repairState: parseRepairState(dictValue["repairState"]),
    details: dictValue["details"],
  };
}

function parseDirectDependencyChange(
  value: unknown,
  sourceName: string,
): DictProjectDependency_DirectChange {
  if (!isRecord(value)) {
    throw new Error(`${sourceName} must be an object.`);
  }

  if (value["change"] === "added") {
    const dictValue = ensureExactRecord(
      value,
      new Set(["componentId", "change", "targetRequirement"]),
      sourceName,
    );
    return {
      componentId: ensureString(dictValue["componentId"], `${sourceName}.componentId`),
      change: "added",
      targetRequirement: ensureString(
        dictValue["targetRequirement"],
        `${sourceName}.targetRequirement`,
      ),
    };
  }

  if (value["change"] === "removed") {
    const dictValue = ensureExactRecord(
      value,
      new Set(["componentId", "change", "previousRequirement"]),
      sourceName,
    );
    return {
      componentId: ensureString(dictValue["componentId"], `${sourceName}.componentId`),
      change: "removed",
      previousRequirement: ensureString(
        dictValue["previousRequirement"],
        `${sourceName}.previousRequirement`,
      ),
    };
  }

  if (value["change"] === "requirementChanged") {
    const dictValue = ensureExactRecord(
      value,
      new Set(["componentId", "change", "previousRequirement", "targetRequirement"]),
      sourceName,
    );
    return {
      componentId: ensureString(dictValue["componentId"], `${sourceName}.componentId`),
      change: "requirementChanged",
      previousRequirement: ensureString(
        dictValue["previousRequirement"],
        `${sourceName}.previousRequirement`,
      ),
      targetRequirement: ensureString(
        dictValue["targetRequirement"],
        `${sourceName}.targetRequirement`,
      ),
    };
  }

  throw new Error(`${sourceName}.change is invalid.`);
}

function parseResolvedDependencyChange(
  value: unknown,
  sourceName: string,
): DictProjectDependency_ResolvedChange {
  if (!isRecord(value)) {
    throw new Error(`${sourceName} must be an object.`);
  }

  const strChange = value["change"];
  if (strChange === "added") {
    const dictValue = ensureExactRecord(
      value,
      new Set(["componentId", "packageName", "displayName", "change", "targetVersion"]),
      sourceName,
    );
    return {
      componentId: ensureString(dictValue["componentId"], `${sourceName}.componentId`),
      packageName: ensureString(dictValue["packageName"], `${sourceName}.packageName`),
      displayName: ensureString(dictValue["displayName"], `${sourceName}.displayName`),
      change: "added",
      targetVersion: ensureString(
        dictValue["targetVersion"],
        `${sourceName}.targetVersion`,
      ),
    };
  }

  if (strChange === "removed") {
    const dictValue = ensureExactRecord(
      value,
      new Set(["componentId", "packageName", "displayName", "change", "previousVersion"]),
      sourceName,
    );
    return {
      componentId: ensureString(dictValue["componentId"], `${sourceName}.componentId`),
      packageName: ensureString(dictValue["packageName"], `${sourceName}.packageName`),
      displayName: ensureString(dictValue["displayName"], `${sourceName}.displayName`),
      change: "removed",
      previousVersion: ensureString(
        dictValue["previousVersion"],
        `${sourceName}.previousVersion`,
      ),
    };
  }

  if (strChange === "upgraded" || strChange === "downgraded") {
    const dictValue = ensureExactRecord(
      value,
      new Set([
        "componentId",
        "packageName",
        "displayName",
        "change",
        "previousVersion",
        "targetVersion",
      ]),
      sourceName,
    );
    return {
      componentId: ensureString(dictValue["componentId"], `${sourceName}.componentId`),
      packageName: ensureString(dictValue["packageName"], `${sourceName}.packageName`),
      displayName: ensureString(dictValue["displayName"], `${sourceName}.displayName`),
      change: strChange,
      previousVersion: ensureString(
        dictValue["previousVersion"],
        `${sourceName}.previousVersion`,
      ),
      targetVersion: ensureString(
        dictValue["targetVersion"],
        `${sourceName}.targetVersion`,
      ),
    };
  }

  throw new Error(`${sourceName}.change is invalid.`);
}

function parseChangeArray<T>(
  value: unknown,
  sourceName: string,
  parser: (item: unknown, itemSourceName: string) => T,
): T[] {
  if (!Array.isArray(value)) {
    throw new Error(`${sourceName} must be an array.`);
  }

  return value.map((item, intIndex) => parser(item, `${sourceName}[${String(intIndex)}]`));
}

export function parseProjectDependencyPlanResult(
  value: unknown,
): DictProtocolResult_ProjectDependencyPlan {
  const dictValue = ensureExactRecord(
    value,
    SET_KEYS_PROJECT_DEPENDENCY_PLAN,
    "Project dependency plan result",
  );
  if (dictValue["status"] !== "projectDependencyPlanCreated") {
    throw new Error("Component Management returned an unsupported dependency plan status.");
  }

  const sourceManifestValue = dictValue["sourceManifest"];
  if (!isRecord(sourceManifestValue)) {
    throw new Error("Project dependency plan sourceManifest must be an object.");
  }
  const sourceProjectType = "id" in sourceManifestValue ? "component" : "flow";

  const targetManifestValue = dictValue["targetManifest"];
  if (!isRecord(targetManifestValue)) {
    throw new Error("Project dependency plan targetManifest must be an object.");
  }
  const targetProjectType = "id" in targetManifestValue ? "component" : "flow";
  if (sourceProjectType !== targetProjectType) {
    throw new Error("Project dependency plan changed the Project type.");
  }

  return {
    status: "projectDependencyPlanCreated",
    planSha256: ensureSha256(dictValue["planSha256"], "Project dependency plan planSha256"),
    sourceManifest: parseProjectManifest(
      sourceManifestValue,
      sourceProjectType,
      "Project dependency plan sourceManifest",
    ),
    sourceComponentsLock: parseOptionalComponentsLock(
      dictValue["sourceComponentsLock"],
      "Project dependency plan sourceComponentsLock",
    ),
    targetManifest: parseProjectManifest(
      targetManifestValue,
      targetProjectType,
      "Project dependency plan targetManifest",
    ),
    targetComponentsLock: parseOptionalComponentsLock(
      dictValue["targetComponentsLock"],
      "Project dependency plan targetComponentsLock",
    ),
    directDependencyChanges: parseChangeArray(
      dictValue["directDependencyChanges"],
      "Project dependency plan directDependencyChanges",
      parseDirectDependencyChange,
    ),
    resolvedComponentChanges: parseChangeArray(
      dictValue["resolvedComponentChanges"],
      "Project dependency plan resolvedComponentChanges",
      parseResolvedDependencyChange,
    ),
  };
}

function parseProjectComponentsFolder(
  value: unknown,
  sourceName: string,
): DictProtocolResult_ComponentsFolder {
  const dictValue = ensureExactRecord(
    value,
    SET_KEYS_PROJECT_COMPONENTS_FOLDER,
    sourceName,
  );
  return {
    componentsFolderPath: ensureString(
      dictValue["componentsFolderPath"],
      `${sourceName}.componentsFolderPath`,
    ),
    componentCount: ensureNonNegativeInteger(
      dictValue["componentCount"],
      `${sourceName}.componentCount`,
    ),
    fileCount: ensureNonNegativeInteger(dictValue["fileCount"], `${sourceName}.fileCount`),
  };
}

export function parseProjectDependencyPlanAppliedResult(
  value: unknown,
): DictProtocolResult_ProjectDependencyPlanApplied {
  const dictValue = ensureExactRecord(
    value,
    SET_KEYS_PROJECT_DEPENDENCY_PLAN_APPLIED,
    "Project dependency plan applied result",
  );
  if (dictValue["status"] !== "projectDependencyPlanApplied") {
    throw new Error(
      "Component Management returned an unsupported dependency apply status.",
    );
  }

  const targetManifestValue = dictValue["targetManifest"];
  if (!isRecord(targetManifestValue)) {
    throw new Error("Project dependency apply targetManifest must be an object.");
  }
  const targetProjectType = "id" in targetManifestValue ? "component" : "flow";

  return {
    status: "projectDependencyPlanApplied",
    planSha256: ensureSha256(
      dictValue["planSha256"],
      "Project dependency apply planSha256",
    ),
    targetManifest: parseProjectManifest(
      targetManifestValue,
      targetProjectType,
      "Project dependency apply targetManifest",
    ),
    targetComponentsLock: parseOptionalComponentsLock(
      dictValue["targetComponentsLock"],
      "Project dependency apply targetComponentsLock",
    ),
    directDependencyChanges: parseChangeArray(
      dictValue["directDependencyChanges"],
      "Project dependency apply directDependencyChanges",
      parseDirectDependencyChange,
    ),
    resolvedComponentChanges: parseChangeArray(
      dictValue["resolvedComponentChanges"],
      "Project dependency apply resolvedComponentChanges",
      parseResolvedDependencyChange,
    ),
    componentsFolder:
      dictValue["componentsFolder"] === null
        ? null
        : parseProjectComponentsFolder(
            dictValue["componentsFolder"],
            "Project dependency apply componentsFolder",
          ),
  };
}

export function parseProjectComponentsRepairedResult(
  value: unknown,
): DictProtocolResult_ProjectComponentsRepaired {
  const dictValue = ensureExactRecord(
    value,
    SET_KEYS_PROJECT_COMPONENTS_REPAIRED,
    "Project Components repaired result",
  );
  if (dictValue["status"] !== "projectComponentsRepaired") {
    throw new Error("Component Management returned an unsupported repair status.");
  }

  return {
    status: "projectComponentsRepaired",
    componentsFolder: parseProjectComponentsFolder(
      dictValue["componentsFolder"],
      "Project Components repaired componentsFolder",
    ),
  };
}
