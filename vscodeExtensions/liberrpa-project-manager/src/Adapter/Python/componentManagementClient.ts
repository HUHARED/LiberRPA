// FileName: componentManagementClient.ts

import type {
  DictComponentManagementWarning,
  DictProtocolDependencyOperation,
  DictProtocolResult_Publish,
  DictProtocolResult_ComponentWheelsImported,
  DictProtocolResult_RepositoryIndexRebuilt,
  DictProtocolResult_RepositoryCatalog,
  DictProtocolResult_ProjectManifestDefaults,
  DictProtocolResult_ProjectDependencyState,
  DictProtocolResult_ProjectDependencyPlan,
  DictProtocolResult_ProjectDependencyPlanApplied,
  DictProtocolResult_ProjectComponentsRepaired,
} from "../../Domain/ComponentManagement/componentManagementTypes";
import { runComponentManagement } from "./componentManagementProcess";
import type {
  DictProtocolRequest,
  DictProtocolError,
  DictProtocolResponse_Raw,
} from "./componentManagementProtocol";
import { parsePublishComponentResult } from "./Result/publishResult";
import {
  parseRepositoryIndexRebuiltResult,
  parseComponentWheelsImportedResult,
  parseRepositoryCatalogResult,
} from "./Result/repositoryResult";
import { parseProjectManifestDefaultsResult } from "./Result/projectManifestResult";
import {
  parseProjectDependencyStateResult,
  parseProjectDependencyPlanResult,
  parseProjectDependencyPlanAppliedResult,
  parseProjectComponentsRepairedResult,
} from "./Result/projectDependencyResult";

export interface Info_ComponentManagement_OperationResult<T> {
  result: T;
  warnings: DictComponentManagementWarning[];
}

export class ComponentManagementOperationError extends Error {
  public readonly operationName: string;
  public readonly code: string;
  public readonly details: Record<string, unknown>;

  public constructor(operationName: string, errorInfo: DictProtocolError) {
    super(errorInfo.message);
    this.name = "ComponentManagementOperationError";
    this.operationName = operationName;
    this.code = errorInfo.code;
    this.details = errorInfo.details;
  }
}

async function runOperation<T>(
  requestInfo: DictProtocolRequest,
  operationName: string,
  parseResult: (value: unknown) => T,
): Promise<Info_ComponentManagement_OperationResult<T>> {
  const response: DictProtocolResponse_Raw = await runComponentManagement(requestInfo);
  if (!response.ok) {
    throw new ComponentManagementOperationError(operationName, response.error);
  }

  return {
    result: parseResult(response.result),
    warnings: response.warnings,
  };
}

export async function publishComponent(
  projectPath: string,
): Promise<Info_ComponentManagement_OperationResult<DictProtocolResult_Publish>> {
  return await runOperation(
    {
      schemaVersion: 1,
      operation: "publishComponent",
      projectPath,
    },
    "Publish Component",
    parsePublishComponentResult,
  );
}

export async function importComponentWheels(
  wheelFilePaths: string[],
): Promise<
  Info_ComponentManagement_OperationResult<DictProtocolResult_ComponentWheelsImported>
> {
  return await runOperation(
    {
      schemaVersion: 1,
      operation: "importComponentWheels",
      wheelFilePaths,
    },
    "Import Component Wheels",
    parseComponentWheelsImportedResult,
  );
}

export async function rebuildRepositoryIndex(): Promise<
  Info_ComponentManagement_OperationResult<DictProtocolResult_RepositoryIndexRebuilt>
> {
  return await runOperation(
    {
      schemaVersion: 1,
      operation: "rebuildRepositoryIndex",
    },
    "Rebuild Repository Index",
    parseRepositoryIndexRebuiltResult,
  );
}

export async function getComponentRepositoryCatalog(): Promise<
  Info_ComponentManagement_OperationResult<DictProtocolResult_RepositoryCatalog>
> {
  return await runOperation(
    {
      schemaVersion: 1,
      operation: "getComponentRepositoryCatalog",
    },
    "Get Component Repository Catalog",
    parseRepositoryCatalogResult,
  );
}

export async function getProjectManifestDefaults(): Promise<
  Info_ComponentManagement_OperationResult<DictProtocolResult_ProjectManifestDefaults>
> {
  return await runOperation(
    {
      schemaVersion: 1,
      operation: "getProjectManifestDefaults",
    },
    "Get Project Manifest Defaults",
    parseProjectManifestDefaultsResult,
  );
}

export async function getProjectDependencyState(
  projectPath: string,
): Promise<
  Info_ComponentManagement_OperationResult<DictProtocolResult_ProjectDependencyState>
> {
  return await runOperation(
    {
      schemaVersion: 1,
      operation: "getProjectDependencyState",
      projectPath,
    },
    "Get Project Dependency State",
    parseProjectDependencyStateResult,
  );
}

export async function buildProjectDependencyPlan(
  projectPath: string,
  dependencyOperation: DictProtocolDependencyOperation,
): Promise<
  Info_ComponentManagement_OperationResult<DictProtocolResult_ProjectDependencyPlan>
> {
  return await runOperation(
    {
      schemaVersion: 1,
      operation: "buildProjectDependencyPlan",
      projectPath,
      dependencyOperation,
    },
    "Build Project Dependency Plan",
    parseProjectDependencyPlanResult,
  );
}

export async function applyProjectDependencyPlan(
  projectPath: string,
  dependencyOperation: DictProtocolDependencyOperation,
  confirmedPlanSha256: string,
): Promise<
  Info_ComponentManagement_OperationResult<DictProtocolResult_ProjectDependencyPlanApplied>
> {
  return await runOperation(
    {
      schemaVersion: 1,
      operation: "applyProjectDependencyPlan",
      projectPath,
      dependencyOperation,
      confirmedPlanSha256,
    },
    "Apply Project Dependency Plan",
    parseProjectDependencyPlanAppliedResult,
  );
}

export async function repairProjectComponents(
  projectPath: string,
): Promise<
  Info_ComponentManagement_OperationResult<DictProtocolResult_ProjectComponentsRepaired>
> {
  return await runOperation(
    {
      schemaVersion: 1,
      operation: "repairProjectComponents",
      projectPath,
    },
    "Repair Project Components",
    parseProjectComponentsRepairedResult,
  );
}
