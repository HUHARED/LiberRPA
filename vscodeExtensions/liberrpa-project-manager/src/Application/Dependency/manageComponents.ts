// FileName: manageComponents.ts

import {
  ComponentManagementOperationError,
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
  repositoryCatalog: DictProtocolResult_RepositoryCatalog | null;
  repositoryCatalogError: ComponentManagementOperationError | null;
  warnings: DictComponentManagementWarning[];
}

const SET_RECOVERABLE_REPOSITORY_CATALOG_ERROR_CODE = new Set([
  "repository_unavailable",
  "repository_rebuild_required",
]);

export async function loadManageComponentsData(
  projectPath: string,
): Promise<Info_ManageComponentsData> {
  // Load the Repository first so its pending transactions are recovered before
  // Project state checks inspect exact Wheel availability for Repair.
  let repositoryCatalog: DictProtocolResult_RepositoryCatalog | null = null;
  let repositoryCatalogError: ComponentManagementOperationError | null = null;
  let arrRepositoryWarning: DictComponentManagementWarning[] = [];

  try {
    const repositoryCatalogResult = await getComponentRepositoryCatalog();
    repositoryCatalog = repositoryCatalogResult.result;
    arrRepositoryWarning = repositoryCatalogResult.warnings;
  } catch (e: unknown) {
    if (
      !(e instanceof ComponentManagementOperationError) ||
      !SET_RECOVERABLE_REPOSITORY_CATALOG_ERROR_CODE.has(e.code)
    ) {
      throw e;
    }
    repositoryCatalogError = e;
  }

  const projectStateResult = await getProjectDependencyState(projectPath);

  return {
    projectState: projectStateResult.result,
    repositoryCatalog,
    repositoryCatalogError,
    warnings: [...arrRepositoryWarning, ...projectStateResult.warnings],
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
