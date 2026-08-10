// FileName: publishComponentStore.ts

import { defineStore } from "pinia";

import type { DictPublishComponentInitialData } from "../../Adapter/Extension/projectManagerMessages";
import type { DictProtocolResult_Publish } from "../../Domain/ComponentManagement/componentManagementTypes";
import type { DictProjectManifest_Component } from "../../Domain/Project/projectTypes";

export const usePublishComponentStore = defineStore("publishComponent", {
  state: () => ({
    projectPath: "",
    manifest: null as DictProjectManifest_Component | null,

    astSnippetsFile: "",
    snippetsJsoncFile: "",
    astSnippetsFileExists: false,
    snippetsJsoncFileExists: false,

    publishResult: null as DictProtocolResult_Publish | null,
    warningMessages: [] as string[],
  }),

  actions: {
    load(initialData: DictPublishComponentInitialData): void {
      this.projectPath = initialData.projectPath;
      this.manifest = initialData.manifest;

      this.astSnippetsFile = initialData.astSnippetsFile;
      this.snippetsJsoncFile = initialData.snippetsJsoncFile;
      this.astSnippetsFileExists = initialData.astSnippetsFileExists;
      this.snippetsJsoncFileExists = initialData.snippetsJsoncFileExists;

      this.publishResult = initialData.publishResult;
      this.warningMessages = initialData.warningMessages;
    },
  },
});
