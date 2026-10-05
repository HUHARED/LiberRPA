// FileName: packageProjectStore.ts

import { defineStore } from "pinia";

import type { DictPackageProjectInitialData } from "../../Adapter/Extension/projectManagerMessages";
import type { DictProtocolResult_ProjectDependencyState } from "../../Domain/ComponentManagement/componentManagementTypes";
import type {
  DictProjectManifest_Flow,
  DictPackageProjectInput,
  DictProjectPackageResult,
} from "../../Domain/Project/projectTypes";
import {
  ConsolePublishStatus,
  type ConsolePublishDepartment,
  type ConsolePublishResult,
} from "../../Domain/Console/consoleTypes";

export const usePackageProjectStore = defineStore("packageProject", {
  state: () => ({
    projectPath: "",
    manifest: null as DictProjectManifest_Flow | null,
    projectDependencyState: null as DictProtocolResult_ProjectDependencyState | null,

    outputFolderPath: "",
    versionSummary: "",
    includeVscodeSettings: false,
    includeProjectTests: false,
    includeGitRepository: false,

    publishToConsole: false,
    consoleDepartmentId: "",
    consoleDepartments: [] as ConsolePublishDepartment[],
    consolePublishingMessage: "",
    consolePublishResult: {
      status: ConsolePublishStatus.NotRequested,
      message: "",
      packageId: null,
    } as ConsolePublishResult,

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
      this.versionSummary = initialData.input.versionSummary;
      this.includeVscodeSettings = initialData.input.includeVscodeSettings;
      this.includeProjectTests = initialData.input.includeProjectTests;
      this.includeGitRepository = initialData.input.includeGitRepository;

      this.publishToConsole = initialData.input.publishToConsole;
      this.consoleDepartmentId = initialData.input.consoleDepartmentId;
      this.consoleDepartments = initialData.consoleDepartments;
      this.consolePublishingMessage = initialData.consolePublishingMessage;
      this.consolePublishResult = initialData.consolePublishResult;

      this.packageFileName = initialData.packageFileName;
      this.packageFileExists = initialData.packageFileExists;

      this.blockingReasons = initialData.blockingReasons;
      this.warningMessages = initialData.warningMessages;
      this.packageResult = initialData.packageResult;
    },

    getInput(): DictPackageProjectInput {
      return {
        outputFolderPath: this.outputFolderPath,
        versionSummary: this.versionSummary,
        includeVscodeSettings: this.includeVscodeSettings,
        includeProjectTests: this.includeProjectTests,
        includeGitRepository: this.includeGitRepository,
        publishToConsole: this.publishToConsole,
        consoleDepartmentId: this.consoleDepartmentId,
      };
    },
  },
});
