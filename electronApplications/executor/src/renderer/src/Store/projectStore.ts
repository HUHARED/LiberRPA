import { defineStore } from "pinia";

import { invokeMain } from "../IPC/ipc";
import { loggerRenderer } from "../Logging/logger";
import type {
  DictColumns_Project_Detail,
  DictColumns_Project_Detail_ToUpdate,
} from "../../../shared/project";

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
      dictDetail_edit: undefined as DictColumns_Project_Detail | undefined,
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
      // Only run it if it's the first swtich to Projects tab, or the data indeed needs to refresh.
      if (this.arrName.length === 0) {
        this.resetVersionAndDetail();

        const arrRows = await invokeMain("selectProjectNames");
        // Use idTemp for Vueify component to sort, get name when click.
        let idTemp = 0;
        this.dictIdToName = {};
        this.arrName = arrRows.map((row) => {
          const dictTemp = {
            title: row.name,
            idTemp: idTemp,
          };
          this.dictIdToName[idTemp] = row.name;
          idTemp += 1;
          return dictTemp;
        });
      }
    },

    async loadProjectVersions(name: string): Promise<void> {
      this.resetVersionAndDetail();

      const arrRows = await invokeMain("selectProjectVersions", name);
      // Initialize versions:
      let idTemp = 0;
      this.dictIdToVersion = {};
      this.arrVersion = arrRows.map((row) => {
        const dictTemp = {
          title: row.version,
          idTemp: idTemp,
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
      // Set it to an empty dictionary for v-if
      this.resetDetail();
    },

    async loadProjectDetail(name: string, version: string): Promise<void> {
      this.resetDetail();
      await this.loadPythonEnvironmentNames();
      const dictRow = await invokeMain("selectProjectDetail", { name, version });
      if (dictRow === undefined) {
        throw new Error(`Project not found: ${name}-${version}`);
      }

      this.dictDetail_edit = {
        id: dictRow.id,
        name: dictRow.name,
        version: dictRow.version,
        description: dictRow.description,
        version_summary: dictRow.version_summary,
        python_environment_name: dictRow.python_environment_name,
        timeout_min: dictRow.timeout_min,
        builtin_log_level: dictRow.builtin_log_level,
        builtin_record_video: dictRow.builtin_record_video === 1,
        builtin_stop_shortcut: dictRow.builtin_stop_shortcut === 1,
        builtin_highlight_ui: dictRow.builtin_highlight_ui === 1,
        custom_prj_args: dictRow.custom_prj_args ? JSON.parse(dictRow.custom_prj_args) : [],
        created_at_ms: dictRow.created_at_ms,
        updated_at_ms: dictRow.updated_at_ms,
      };
      // loggerRenderer.debug(JSON.stringify(this.dictDetail, null, 2));
      this.detailCache_edit = JSON.stringify(this.dictDetail_edit);
    },

    async saveProjectDetail(): Promise<void> {
      if (this.dictDetail_edit !== undefined) {
        const dictTemp: DictColumns_Project_Detail_ToUpdate = {
          id: this.dictDetail_edit.id,
          name: this.dictDetail_edit.name,
          version: this.dictDetail_edit.version,
          description: this.dictDetail_edit.description,
          version_summary: this.dictDetail_edit.version_summary,
          python_environment_name: this.dictDetail_edit.python_environment_name,
          timeout_min: this.dictDetail_edit.timeout_min,
          builtin_log_level: this.dictDetail_edit.builtin_log_level,
          builtin_record_video: this.dictDetail_edit.builtin_record_video ? 1 : 0,
          builtin_stop_shortcut: this.dictDetail_edit.builtin_stop_shortcut ? 1 : 0,
          builtin_highlight_ui: this.dictDetail_edit.builtin_highlight_ui ? 1 : 0,
          custom_prj_args: JSON.stringify(this.dictDetail_edit.custom_prj_args),
        };
        await invokeMain("updateProjectDetail", dictTemp);
        // Then the vue file will refresh project detail due to the name, version variables are managed by it.
      }
    },

    async loadBoundSchedules(): Promise<void> {
      if (this.dictDetail_edit !== undefined) {
        const arrRows = await invokeMain(
          "selectProjectBoundSchedules",
          this.dictDetail_edit.id,
        );
        this.arrBoundSchedule = arrRows.map((row) => {
          const dictTemp = {
            title: row.name,
          };
          return dictTemp;
        });
      }
    },

    async deleteProject(): Promise<void> {
      if (this.dictDetail_edit !== undefined) {
        loggerRenderer.info(
          `Delete project: ${this.dictDetail_edit.id}-${this.dictDetail_edit.name}-${this.dictDetail_edit.version}`,
        );
        await invokeMain("deleteProject", this.dictDetail_edit.id);

        await invokeMain("deleteExecutorPackage", {
          name: this.dictDetail_edit.name,
          version: this.dictDetail_edit.version,
        });

        // Update the list.
        this.arrName = [];
        await this.loadProjectNames();
        this.showDialog_delete = false;
        this.arrBoundSchedule = [];
      }
    },
  },
});
