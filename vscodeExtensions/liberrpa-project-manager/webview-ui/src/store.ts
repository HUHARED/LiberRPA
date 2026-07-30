// FileName: store.ts

import { defineStore } from "pinia";

import type {
  Str_ProjectType,
  DictProtocolDependencyOperation,
  DictProtocolResult_RepositoryCatalog,
  DictProtocolResult_ProjectDependencyState,
  DictProtocolResult_ProjectDependencyPlan,
} from "./componentManagement/protocol";
import type {
  Theme,
  ProjectManagerOperation,
  DictProjectTemplateInfo,
  DictCreateProjectInitialData,
  DictManageComponentsInitialData,
} from "./extensionMessages";

type AlertType = "info" | "warning" | "error";

export const useProjectManagerStore = defineStore("projectManager", {
  state: () => ({
    loaded: false as boolean,
    busy: false as boolean,
    theme: "light" as Theme,
    operation: null as ProjectManagerOperation | null,

    templates: [] as DictProjectTemplateInfo[],
    projectType: "flow" as Str_ProjectType,
    templateName: "" as string,
    targetFolder: "" as string,
    projectFolderName: "" as string,
    version: "1.0.0" as string,
    description: "" as string,
    packageName: "" as string,
    displayName: "" as string,

    projectDependencyState: null as DictProtocolResult_ProjectDependencyState | null,
    repositoryCatalog: null as DictProtocolResult_RepositoryCatalog | null,
    manageWarningMessages: [] as string[],
    dependencyOperation: null as DictProtocolDependencyOperation | null,
    dependencyPlan: null as DictProtocolResult_ProjectDependencyPlan | null,
    dependencyPlanWarningMessages: [] as string[],

    showAlert: false as boolean,
    alertType: "info" as AlertType,
    alertMessage: "" as string,
  }),

  actions: {
    loadCreateProject(initialData: DictCreateProjectInitialData): void {
      this.loaded = true;
      this.busy = false;
      this.theme = initialData.theme;
      this.operation = "createProject";
      this.templates = initialData.templates;
      this.targetFolder = "";
      this.projectFolderName = "";
      this.packageName = "";
      this.displayName = "";
      this.projectDependencyState = null;
      this.repositoryCatalog = null;
      this.clearDependencyPlan();
      this.clearAlert();

      const initialTemplate =
        initialData.templates.find((item) => item.projectType === "flow") ??
        initialData.templates[0];

      if (initialTemplate === undefined) {
        this.templateName = "";
        return;
      }

      this.projectType = initialTemplate.projectType;
      this.applyTemplate(initialTemplate);
    },

    loadManageComponents(initialData: DictManageComponentsInitialData): void {
      this.loaded = true;
      this.busy = false;
      this.theme = initialData.theme;
      this.operation = "manageComponents";
      this.projectDependencyState = initialData.projectState;
      this.repositoryCatalog = initialData.repositoryCatalog;
      this.manageWarningMessages = initialData.warningMessages;
      this.clearDependencyPlan();
      this.clearAlert();

      if (initialData.notification !== undefined) {
        this.showMessage(initialData.notification.type, initialData.notification.message);
      }
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

    selectProjectType(projectType: Str_ProjectType): void {
      this.projectType = projectType;

      const template = this.templates.find((item) => item.projectType === projectType);
      if (template !== undefined) {
        this.applyTemplate(template);
      } else {
        this.templateName = "";
      }
    },

    selectTemplate(templateName: string): void {
      const template = this.templates.find((item) => item.templateName === templateName);
      if (template !== undefined) {
        this.projectType = template.projectType;
        this.applyTemplate(template);
      }
    },

    applyTemplate(template: DictProjectTemplateInfo): void {
      this.templateName = template.templateName;
      this.version = template.defaultVersion;
      this.description = template.defaultDescription;
    },

    showMessage(type: AlertType, message: string): void {
      this.alertType = type;
      this.alertMessage = message;
      this.showAlert = true;
    },

    clearAlert(): void {
      this.showAlert = false;
      this.alertMessage = "";
    },
  },
});
