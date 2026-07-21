// FileName: store.ts

import { defineStore } from "pinia";
import type { AlertType } from "./interface";
import type {
  CreateProjectLoadContext,
  ProjectManagerOperation,
  ProjectManagerTheme,
  ProjectTemplateInfo,
  ProjectType,
} from "./webviewMessages";

export const useProjectManagerStore = defineStore("projectManager", {
  state: () => ({
    loaded: false as boolean,
    busy: false as boolean,
    operation: "createProject" as ProjectManagerOperation,
    theme: "light" as ProjectManagerTheme,

    templates: [] as ProjectTemplateInfo[],
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
    loadCreateProject(context: CreateProjectLoadContext): void {
      this.loaded = true;
      this.busy = false;
      this.operation = "createProject";
      this.theme = context.theme;
      this.templates = context.templates;
      this.targetFolder = "";
      this.projectFolderName = "";
      this.packageName = "";
      this.displayName = "";
      this.clearAlert();

      const initialTemplate =
        context.templates.find((item) => item.projectType === "flow") ??
        context.templates[0];

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

    applyTemplate(template: ProjectTemplateInfo): void {
      this.templateName = template.templateName;
      this.version = template.version;
      this.description = template.description;
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
