// FileName: packageProjectStore.ts

import { defineStore } from "pinia";

import type { DictPackageProjectInitialData } from "../../Adapter/Extension/projectManagerMessages";
import type { DictProtocolResult_ProjectDependencyState } from "../../Domain/ComponentManagement/componentManagementTypes";
import type {
  DictProjectManifest_Flow,
  DictPackageProjectInput,
  DictProjectPackageResult,
} from "../../Domain/Project/projectTypes";

export const usePackageProjectStore = defineStore("packageProject", {
  state: () => ({
    projectPath: "",
    manifest: null as DictProjectManifest_Flow | null,
    projectDependencyState: null as DictProtocolResult_ProjectDependencyState | null,

    outputFolderPath: "",
    includeVscodeSettings: false,
    includeGitRepository: false,
    packageFileName: null as string | null,
    packageFileExists: false,

    blockingReasons: [] as string[],
    warningMessages: [] as string[],
    packageResult: null as DictProjectPackageResult | null,
  }),

  actions: {
    load(initialData: DictPackageProjectInitialData): void {
      this.projectPath = initialData.projectPath;
      this.manifest = initialData.manifest;
      this.projectDependencyState = initialData.projectDependencyState;

      this.outputFolderPath = initialData.input.outputFolderPath;
      this.includeVscodeSettings = initialData.input.includeVscodeSettings;
      this.includeGitRepository = initialData.input.includeGitRepository;
      this.packageFileName = initialData.packageFileName;
      this.packageFileExists = initialData.packageFileExists;

      this.blockingReasons = initialData.blockingReasons;
      this.warningMessages = initialData.warningMessages;
      this.packageResult = initialData.packageResult;
    },

    getInput(): DictPackageProjectInput {
      return {
        outputFolderPath: this.outputFolderPath,
        includeVscodeSettings: this.includeVscodeSettings,
        includeGitRepository: this.includeGitRepository,
      };
    },
  },
});
