// FileName: createProjectStore.ts

import { defineStore } from "pinia";

import type { DictCreateProjectInitialData } from "../../Adapter/Extension/projectManagerMessages";
import type {
  Str_ProjectType,
  DictProjectTemplateInfo,
} from "../../Domain/Project/projectTypes";

export const useCreateProjectStore = defineStore("createProject", {
  state: () => ({
    templates: [] as DictProjectTemplateInfo[],

    templateName: "",
    projectType: "flow" as Str_ProjectType,

    targetFolderPath: "",
    projectFolderName: "",

    version: "1.0.0",
    description: "",
    packageName: "",
    displayName: "",
  }),

  actions: {
    load(initialData: DictCreateProjectInitialData): void {
      this.templates = initialData.templates;
      this.targetFolderPath = "";
      this.projectFolderName = "";
      this.packageName = "";
      this.displayName = "";

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

    selectProjectType(projectType: Str_ProjectType): void {
      this.projectType = projectType;
      const template = this.templates.find((item) => item.projectType === projectType);
      if (template === undefined) {
        this.templateName = "";
      } else {
        this.applyTemplate(template);
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
  },
});
