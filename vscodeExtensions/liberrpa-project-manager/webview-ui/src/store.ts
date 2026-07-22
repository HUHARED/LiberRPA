// FileName: store.ts

import { defineStore } from "pinia";

import type {
  Theme,
  ProjectType,
  DictCreateProjectInitialData,
  DictProjectTemplateInfo,
} from "./extensionMessages";

type AlertType = "info" | "warning" | "error";

export const useProjectManagerStore = defineStore("projectManager", {
  state: () => ({
    loaded: false as boolean,
    busy: false as boolean,
    theme: "light" as Theme,

    templates: [] as DictProjectTemplateInfo[],
    projectType: "flow" as ProjectType,
    templateName: "" as string,
    targetFolder: "" as string,
    projectFolderName: "" as string,
    version: "1.0.0" as string,
    description: "" as string,
    packageName: "" as string,
    displayName: "" as string,

    showAlert: false as boolean,
    alertType: "info" as AlertType,
    alertMessage: "" as string,
  }),

  actions: {
    loadCreateProject(initialData: DictCreateProjectInitialData): void {
      this.loaded = true;
      this.busy = false;
      this.theme = initialData.theme;
      this.templates = initialData.templates;
      this.targetFolder = "";
      this.projectFolderName = "";
      this.packageName = "";
      this.displayName = "";
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

    selectProjectType(projectType: ProjectType): void {
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
