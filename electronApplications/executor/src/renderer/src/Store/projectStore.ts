import { defineStore } from "pinia";

import { invokeMain } from "../IPC/ipc";
import { loggerRenderer } from "../Logging/logger";
import type { DictProjectDetail, DictProjectSettingsUpdate } from "../../../shared/project";

export const useProjectStore = defineStore("project", {
  state: () => {
    return {
      // Name list
      arrName: [] as { title: string; idTemp: number }[],
      dictIdToName: {} as { [idTemp: number]: string },

      // Version list
      arrVersion: [] as { title: string; idTemp: number }[],
      dictIdToVersion: {} as { [idTemp: number]: string },

      // Python environments
      arrPythonEnvironmentName: [] as string[],

      // Detail
      dictDetail_edit: undefined as DictProjectDetail | undefined,
      detailCache_edit: undefined as string | undefined,

      // Delete dialog
      showDialog_delete: false as boolean,
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
        let idTemp = 0;
        this.dictIdToName = {};
        this.arrName = arrRows.map((row) => {
          const dictTemp = {
            title: row.name,
            idTemp,
          };
          this.dictIdToName[idTemp] = row.name;
          idTemp += 1;
          return dictTemp;
        });
      }
    },

    async loadProjectVersions(name: string): Promise<void> {
      this.resetVersionAndDetail();

      const arrRows = await invokeMain("getProjectVersions", name);
      let idTemp = 0;
      this.dictIdToVersion = {};
      this.arrVersion = arrRows.map((row) => {
        const dictTemp = {
          title: row.version,
          idTemp,
        };
        this.dictIdToVersion[idTemp] = row.version;
        idTemp += 1;
        return dictTemp;
      });
    },

    resetDetail(): void {
      this.detailCache_edit = undefined;
      this.dictDetail_edit = undefined;
    },

    resetVersionAndDetail(): void {
      this.arrVersion = [];
      this.resetDetail();
    },

    async loadProjectDetail(name: string, version: string): Promise<void> {
      this.resetDetail();
      await this.loadPythonEnvironmentNames();
      const dictDetail = await invokeMain("getProjectDetail", { name, version });
      if (dictDetail === undefined) {
        throw new Error(`Project not found: ${name}-${version}`);
      }

      this.dictDetail_edit = dictDetail;
      this.detailCache_edit = JSON.stringify(this.dictDetail_edit);
    },

    async saveProjectSettings(): Promise<void> {
      if (this.dictDetail_edit === undefined) {
        return;
      }

      const dictTemp: DictProjectSettingsUpdate = {
        id: this.dictDetail_edit.id,
        python_environment_name: this.dictDetail_edit.python_environment_name,
        timeout_min: this.dictDetail_edit.timeout_min,
        builtin_log_level: this.dictDetail_edit.builtin_log_level,
        builtin_record_video: this.dictDetail_edit.builtin_record_video,
        builtin_stop_shortcut: this.dictDetail_edit.builtin_stop_shortcut,
        builtin_highlight_ui: this.dictDetail_edit.builtin_highlight_ui,
        custom_prj_args: this.dictDetail_edit.custom_prj_args,
      };
      await invokeMain("saveProjectSettings", dictTemp);
    },

    async loadBoundSchedules(): Promise<void> {
      if (this.dictDetail_edit !== undefined) {
        const arrRows = await invokeMain(
          "getProjectBoundSchedules",
          this.dictDetail_edit.id,
        );
        this.arrBoundSchedule = arrRows.map((row) => ({ title: row.name }));
      }
    },

    async deleteProject(): Promise<void> {
      if (this.dictDetail_edit !== undefined) {
        loggerRenderer.info(
          `Delete project: ${this.dictDetail_edit.id}-${this.dictDetail_edit.name}-${this.dictDetail_edit.version}`,
        );
        await invokeMain("deleteProject", this.dictDetail_edit.id);

        this.arrName = [];
        await this.loadProjectNames();
        this.showDialog_delete = false;
        this.arrBoundSchedule = [];
      }
    },
  },
});
