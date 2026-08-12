// FileName: componentManagementStore.ts

import { defineStore } from "pinia";

import type {
  DictManageComponentsInitialData,
  DictManageComponentsRepositoryCatalogError,
} from "../../Adapter/Extension/projectManagerMessages";
import type {
  DictProtocolDependencyOperation,
  DictProtocolResult_RepositoryCatalog,
  DictProtocolResult_ProjectDependencyState,
  DictProtocolResult_ProjectDependencyPlan,
} from "../../Domain/ComponentManagement/componentManagementTypes";

export const useComponentManagementStore = defineStore("componentManagement", {
  state: () => ({
    projectDependencyState: null as DictProtocolResult_ProjectDependencyState | null,
    repositoryCatalog: null as DictProtocolResult_RepositoryCatalog | null,
    repositoryCatalogError: null as DictManageComponentsRepositoryCatalogError | null,
    warningMessages: [] as string[],
    dependencyOperation: null as DictProtocolDependencyOperation | null,
    dependencyPlan: null as DictProtocolResult_ProjectDependencyPlan | null,
    dependencyPlanWarningMessages: [] as string[],
  }),

  actions: {
    load(initialData: DictManageComponentsInitialData): void {
      this.projectDependencyState = initialData.projectState;
      this.repositoryCatalog = initialData.repositoryCatalog;
      this.repositoryCatalogError = initialData.repositoryCatalogError;
      this.warningMessages = initialData.warningMessages;
      this.clearDependencyPlan();
    },

    setDependencyPlan(
      dependencyOperation: DictProtocolDependencyOperation,
      plan: DictProtocolResult_ProjectDependencyPlan,
      warningMessages: string[],
    ): void {
      this.dependencyOperation = dependencyOperation;
      this.dependencyPlan = plan;
      this.dependencyPlanWarningMessages = warningMessages;
    },

    clearDependencyPlan(): void {
      this.dependencyOperation = null;
      this.dependencyPlan = null;
      this.dependencyPlanWarningMessages = [];
    },
  },
});
