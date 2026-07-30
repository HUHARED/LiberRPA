// FileName: operations.ts

import type {
  DictComponentManagementWarning,
  DictProtocolDependencyOperation,
  DictProtocolResult_RepositoryCatalog,
  DictProtocolResult_ProjectDependencyState,
  DictProtocolResult_ProjectDependencyPlan,
  DictProtocolResult_ProjectDependencyPlanApplied,
  DictProtocolResult_ProjectComponentsRepaired,
  DictProtocolError,
  DictProtocolSuccess_Raw,
  DictProtocolResponse_Raw,
} from "./protocol";
import { runComponentManagement } from "./process";
import {
  parseProjectDependencyStateResult,
  parseProjectDependencyPlanResult,
  parseProjectDependencyPlanAppliedResult,
  parseProjectComponentsRepairedResult,
} from "./projectDependencyResult";
import { parseRepositoryCatalogResult } from "./repositoryResult";

export interface Info_ComponentManagement_OperationResult<T> {
  result: T;
  warnings: DictComponentManagementWarning[];
}

export class ComponentManagementOperationError extends Error {
  public readonly code: string;
  public readonly details: Record<string, unknown>;

  public constructor(operationName: string, errorInfo: DictProtocolError) {
    super(`${operationName} failed [${errorInfo.code}]: ${errorInfo.message}`);
    this.name = "ComponentManagementOperationError";
    this.code = errorInfo.code;
    this.details = errorInfo.details;
  }
}

function getSuccessResponse(
  response: DictProtocolResponse_Raw,
  operationName: string,
): DictProtocolSuccess_Raw {
  if (!response.ok) {
    throw new ComponentManagementOperationError(operationName, response.error);
  }

  return response;
}

export async function getComponentRepositoryCatalog(): Promise<
  Info_ComponentManagement_OperationResult<DictProtocolResult_RepositoryCatalog>
> {
  const response = getSuccessResponse(
    await runComponentManagement({
      schemaVersion: 1,
      operation: "getComponentRepositoryCatalog",
    }),
    "Get Component Repository Catalog",
  );

  return {
    result: parseRepositoryCatalogResult(response.result),
    warnings: response.warnings,
  };
}

export async function getProjectDependencyState(
  projectPath: string,
): Promise<
  Info_ComponentManagement_OperationResult<DictProtocolResult_ProjectDependencyState>
> {
  const response = getSuccessResponse(
    await runComponentManagement({
      schemaVersion: 1,
      operation: "getProjectDependencyState",
      projectPath,
    }),
    "Get Project Dependency State",
  );

  return {
    result: parseProjectDependencyStateResult(response.result),
    warnings: response.warnings,
  };
}

export async function buildProjectDependencyPlan(
  projectPath: string,
  dependencyOperation: DictProtocolDependencyOperation,
): Promise<
  Info_ComponentManagement_OperationResult<DictProtocolResult_ProjectDependencyPlan>
> {
  const response = getSuccessResponse(
    await runComponentManagement({
      schemaVersion: 1,
      operation: "buildProjectDependencyPlan",
      projectPath,
      dependencyOperation,
    }),
    "Build Project Dependency Plan",
  );

  return {
    result: parseProjectDependencyPlanResult(response.result),
    warnings: response.warnings,
  };
}

export async function applyProjectDependencyPlan(
  projectPath: string,
  dependencyOperation: DictProtocolDependencyOperation,
  confirmedPlanSha256: string,
): Promise<
  Info_ComponentManagement_OperationResult<DictProtocolResult_ProjectDependencyPlanApplied>
> {
  const response = getSuccessResponse(
    await runComponentManagement({
      schemaVersion: 1,
      operation: "applyProjectDependencyPlan",
      projectPath,
      dependencyOperation,
      confirmedPlanSha256,
    }),
    "Apply Project Dependency Plan",
  );

  return {
    result: parseProjectDependencyPlanAppliedResult(response.result),
    warnings: response.warnings,
  };
}

export async function repairProjectComponents(
  projectPath: string,
): Promise<
  Info_ComponentManagement_OperationResult<DictProtocolResult_ProjectComponentsRepaired>
> {
  const response = getSuccessResponse(
    await runComponentManagement({
      schemaVersion: 1,
      operation: "repairProjectComponents",
      projectPath,
    }),
    "Repair Project Components",
  );

  return {
    result: parseProjectComponentsRepairedResult(response.result),
    warnings: response.warnings,
  };
}
