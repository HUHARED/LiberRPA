// FileName: packageStore.ts

import { defineStore } from "pinia";

import { invokeMain } from "../IPC/ipc";
import { loggerRenderer } from "../Logging/logger";
import type { PackageDetails, PackageSettingsUpdate } from "../../../shared/package";

export const usePackageStore = defineStore("package", {
  state: () => {
    return {
      arrProjectName: [] as { title: string; value: string }[],
      arrProjectVersion: [] as { title: string; value: string }[],
      arrPythonEnvironmentName: [] as string[],
      intSelectionRevision: 0,

      dictDetailEdit: undefined as PackageDetails | undefined,
      strDetailCacheEdit: undefined as string | undefined,

      // Delete dialog
      showDeleteDialog: false as boolean,
      arrBoundSchedule: [] as { title: string }[],
    };
  },
  actions: {
    async loadPythonEnvironmentNames(): Promise<void> {
      this.arrPythonEnvironmentName = await invokeMain("getPythonEnvironmentNames");
    },

    async loadProjectNames(): Promise<void> {
      if (this.arrProjectName.length === 0) {
        this.resetVersionAndDetail();

        const arrRows = await invokeMain("getProjectNames");
        this.arrProjectName = arrRows.map((projectName) => ({
          title: projectName,
          value: projectName,
        }));
      }
    },

    async loadProjectVersions(projectName: string): Promise<void> {
      const intRevision = ++this.intSelectionRevision;
      this.arrProjectVersion = [];
      this.strDetailCacheEdit = undefined;
      this.dictDetailEdit = undefined;

      const arrRows = await invokeMain("getProjectVersions", projectName);
      if (intRevision !== this.intSelectionRevision) {
        return;
      }

      this.arrProjectVersion = arrRows.map((projectVersion) => ({
        title: projectVersion,
        value: projectVersion,
      }));
    },

    resetDetail(): void {
      this.intSelectionRevision += 1;
      this.strDetailCacheEdit = undefined;
      this.dictDetailEdit = undefined;
    },

    resetVersionAndDetail(): void {
      this.intSelectionRevision += 1;
      this.arrProjectVersion = [];
      this.strDetailCacheEdit = undefined;
      this.dictDetailEdit = undefined;
    },

    async loadPackageDetails(projectName: string, projectVersion: string): Promise<void> {
      const intRevision = ++this.intSelectionRevision;
      this.strDetailCacheEdit = undefined;
      this.dictDetailEdit = undefined;

      await this.loadPythonEnvironmentNames();
      if (intRevision !== this.intSelectionRevision) {
        return;
      }

      const dictDetail = await invokeMain("getPackageDetails", {
        project_name: projectName,
        project_version: projectVersion,
      });
      if (intRevision !== this.intSelectionRevision) {
        return;
      }

      if (dictDetail === undefined) {
        throw new Error(`Package not found: ${projectName}-${projectVersion}`);
      }

      this.dictDetailEdit = dictDetail;
      this.strDetailCacheEdit = JSON.stringify(dictDetail);
    },

    async savePackageSettings(): Promise<void> {
      if (this.dictDetailEdit === undefined) {
        return;
      }

      const dictTemp: PackageSettingsUpdate = {
        id: this.dictDetailEdit.id,
        python_environment_name: this.dictDetailEdit.python_environment_name,
        max_retry_count: this.dictDetailEdit.max_retry_count,
        timeout_min: this.dictDetailEdit.timeout_min,
        builtin_log_level: this.dictDetailEdit.builtin_log_level,
        builtin_record_video: this.dictDetailEdit.builtin_record_video,
        builtin_stop_shortcut: this.dictDetailEdit.builtin_stop_shortcut,
        builtin_highlight_ui: this.dictDetailEdit.builtin_highlight_ui,
        custom_prj_args: this.dictDetailEdit.custom_prj_args,
      };
      await invokeMain("savePackageSettings", dictTemp);
    },

    async loadBoundSchedules(): Promise<void> {
      const currentDetail = this.dictDetailEdit;
      if (currentDetail === undefined) {
        return;
      }

      const arrRows = await invokeMain("getPackageBoundSchedules", currentDetail.id);
      if (this.dictDetailEdit !== currentDetail) {
        return;
      }
      this.arrBoundSchedule = arrRows.map((row) => ({ title: row.name }));
    },

    async deletePackage(): Promise<void> {
      if (this.dictDetailEdit !== undefined) {
        loggerRenderer.info(
          `Delete Package: ${this.dictDetailEdit.id}-${this.dictDetailEdit.project_name}-${this.dictDetailEdit.project_version}`,
        );
        await invokeMain("deletePackage", this.dictDetailEdit.id);

        this.arrProjectName = [];
        await this.loadProjectNames();
        this.showDeleteDialog = false;
        this.arrBoundSchedule = [];
      }
    },
  },
});
