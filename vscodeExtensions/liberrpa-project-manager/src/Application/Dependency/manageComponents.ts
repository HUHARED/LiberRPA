// FileName: manageComponents.ts

import {
  ComponentManagementOperationError,
  getComponentRepositoryCatalog,
  getProjectDependencyState,
} from "../../Adapter/Python/componentManagementClient";
import type {
  DictComponentManagementWarning,
  DictProtocolResult_RepositoryCatalog,
  DictProtocolResult_ProjectDependencyState,
} from "../../Domain/ComponentManagement/componentManagementTypes";

interface ManageComponentsData {
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
): Promise<ManageComponentsData> {
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
