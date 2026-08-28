// FileName: projectStore.ts

import { defineStore } from "pinia";

import { invokeMain } from "../IPC/ipc";
import { loggerRenderer } from "../Logging/logger";
import type {
  Dict_ProjectDetail,
  Dict_ProjectSettingsUpdate,
} from "../../../shared/project";

export const useProjectStore = defineStore("project", {
  state: () => {
    return {
      arrName: [] as { title: string; value: string }[],
      arrVersion: [] as { title: string; value: string }[],
      arrPythonEnvironmentName: [] as string[],
      intSelectionRevision: 0,

      dictDetailEdit: undefined as Dict_ProjectDetail | undefined,
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
      if (this.arrName.length === 0) {
        this.resetVersionAndDetail();

        const arrRows = await invokeMain("getProjectNames");
        this.arrName = arrRows.map((row) => ({
          title: row.name,
          value: row.name,
        }));
      }
    },

    async loadProjectVersions(name: string): Promise<void> {
      const intRevision = ++this.intSelectionRevision;
      this.arrVersion = [];
      this.strDetailCacheEdit = undefined;
      this.dictDetailEdit = undefined;

      const arrRows = await invokeMain("getProjectVersions", name);
      if (intRevision !== this.intSelectionRevision) {
        return;
      }

      this.arrVersion = arrRows.map((row) => ({
        title: row.version,
        value: row.version,
      }));
    },

    resetDetail(): void {
      this.intSelectionRevision += 1;
      this.strDetailCacheEdit = undefined;
      this.dictDetailEdit = undefined;
    },

    resetVersionAndDetail(): void {
      this.intSelectionRevision += 1;
      this.arrVersion = [];
      this.strDetailCacheEdit = undefined;
      this.dictDetailEdit = undefined;
    },

    async loadProjectDetail(name: string, version: string): Promise<void> {
      const intRevision = ++this.intSelectionRevision;
      this.strDetailCacheEdit = undefined;
      this.dictDetailEdit = undefined;

      await this.loadPythonEnvironmentNames();
      if (intRevision !== this.intSelectionRevision) {
        return;
      }

      const dictDetail = await invokeMain("getProjectDetail", { name, version });
      if (intRevision !== this.intSelectionRevision) {
        return;
      }

      if (dictDetail === undefined) {
        throw new Error(`Project not found: ${name}-${version}`);
      }

      this.dictDetailEdit = dictDetail;
      this.strDetailCacheEdit = JSON.stringify(dictDetail);
    },

    async saveProjectSettings(): Promise<void> {
      if (this.dictDetailEdit === undefined) {
        return;
      }

      const dictTemp: Dict_ProjectSettingsUpdate = {
        id: this.dictDetailEdit.id,
        python_environment_name: this.dictDetailEdit.python_environment_name,
        timeout_min: this.dictDetailEdit.timeout_min,
        builtin_log_level: this.dictDetailEdit.builtin_log_level,
        builtin_record_video: this.dictDetailEdit.builtin_record_video,
        builtin_stop_shortcut: this.dictDetailEdit.builtin_stop_shortcut,
        builtin_highlight_ui: this.dictDetailEdit.builtin_highlight_ui,
        custom_prj_args: this.dictDetailEdit.custom_prj_args,
      };
      await invokeMain("saveProjectSettings", dictTemp);
    },

    async loadBoundSchedules(): Promise<void> {
      const currentDetail = this.dictDetailEdit;
      if (currentDetail === undefined) {
        return;
      }

      const arrRows = await invokeMain("getProjectBoundSchedules", currentDetail.id);
      if (this.dictDetailEdit !== currentDetail) {
        return;
      }
      this.arrBoundSchedule = arrRows.map((row) => ({ title: row.name }));
    },

    async deleteProject(): Promise<void> {
      if (this.dictDetailEdit !== undefined) {
        loggerRenderer.info(
          `Delete project: ${this.dictDetailEdit.id}-${this.dictDetailEdit.name}-${this.dictDetailEdit.version}`,
        );
        await invokeMain("deleteProject", this.dictDetailEdit.id);

        this.arrName = [];
        await this.loadProjectNames();
        this.showDeleteDialog = false;
        this.arrBoundSchedule = [];
      }
    },
  },
});
