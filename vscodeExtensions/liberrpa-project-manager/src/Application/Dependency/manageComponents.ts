// FileName: manageComponents.ts

import {
  getComponentRepositoryCatalog,
  getProjectDependencyState,
  buildProjectDependencyPlan,
  applyProjectDependencyPlan,
  repairProjectComponents,
} from "../../Adapter/Python/componentManagementClient";
import type { Info_ComponentManagement_OperationResult } from "../../Adapter/Python/componentManagementClient";
import type {
  DictComponentManagementWarning,
  DictProtocolDependencyOperation,
  DictProtocolResult_RepositoryCatalog,
  DictProtocolResult_ProjectDependencyState,
  DictProtocolResult_ProjectDependencyPlan,
  DictProtocolResult_ProjectDependencyPlanApplied,
  DictProtocolResult_ProjectComponentsRepaired,
} from "../../Domain/ComponentManagement/componentManagementTypes";

interface Info_ManageComponentsData {
  projectState: DictProtocolResult_ProjectDependencyState;
  repositoryCatalog: DictProtocolResult_RepositoryCatalog;
  warnings: DictComponentManagementWarning[];
}

export async function loadManageComponentsData(
  projectPath: string,
): Promise<Info_ManageComponentsData> {
  // Load the Repository first so its pending transactions are recovered before
  // Project state checks inspect exact Wheel availability for Repair.
  const repositoryCatalogResult = await getComponentRepositoryCatalog();
  const projectStateResult = await getProjectDependencyState(projectPath);

  return {
    projectState: projectStateResult.result,
    repositoryCatalog: repositoryCatalogResult.result,
    warnings: [...repositoryCatalogResult.warnings, ...projectStateResult.warnings],
  };
}

export async function createProjectDependencyPlan(
  projectPath: string,
  dependencyOperation: DictProtocolDependencyOperation,
): Promise<
  Info_ComponentManagement_OperationResult<DictProtocolResult_ProjectDependencyPlan>
> {
  return await buildProjectDependencyPlan(projectPath, dependencyOperation);
}

export async function confirmProjectDependencyPlan(
  projectPath: string,
  dependencyOperation: DictProtocolDependencyOperation,
  confirmedPlanSha256: string,
): Promise<
  Info_ComponentManagement_OperationResult<DictProtocolResult_ProjectDependencyPlanApplied>
> {
  return await applyProjectDependencyPlan(
    projectPath,
    dependencyOperation,
    confirmedPlanSha256,
  );
}

export async function repairProjectComponentFolder(
  projectPath: string,
): Promise<
  Info_ComponentManagement_OperationResult<DictProtocolResult_ProjectComponentsRepaired>
> {
  return await repairProjectComponents(projectPath);
}
