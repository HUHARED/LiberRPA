// FileName: store.ts

import { defineStore } from "pinia";
import { CronExpressionParser } from "cron-parser";

import { loggerRenderer, invokeMain } from "./ipcOfRenderer";
import { sanitizeJsonObj } from "./commonFunc";
import {
  formatTimestampForDateTimeLocal,
  getSystemTimezone,
  parseDateTimeLocalToTimestamp,
} from "./time";
import type {
  DictExecutorConfig,
  DictColumns_Project_Detail_DB,
  DictColumns_Project_Detail,
  DictColumns_Project_Detail_ToUpdate,
  DictColumns_Project_Detail_Run,
  DictColumns_Scheduler_ListItem_DB,
  DictColumns_Scheduler_ListItem,
  DictColumns_Scheduler_Detail_DB,
  DictColumns_Scheduler_Detail,
  DictColumns_Scheduler_Detail_ToUpdate,
  DictColumns_Scheduler_Detail_BeforeInsert,
  DictColumns_Scheduler_Detail_ToInsert,
  DictColumns_History_ListItem_DB,
  DictColumns_History_ListItem_Limit_DB,
  Dict_History_Options,
  Dict_History_Options_Component,
  Dict_History_Search,
  Dict_TaskQueue_ListItem,
  TypeTaskHistoryStatus,
} from "../../shared/interface";

let intLastCleanupAtMs = Date.now();

function getSchedulerPeriodTimestamps({
  periodStart,
  periodEnd,
  timezone,
}: {
  periodStart: string;
  periodEnd: string;
  timezone: string;
}): { intPeriodStartMs: number; intPeriodEndMs: number } {
  const intPeriodStartMs = parseDateTimeLocalToTimestamp(periodStart, timezone);
  const intPeriodEndMs = parseDateTimeLocalToTimestamp(periodEnd, timezone);

  if (intPeriodStartMs === undefined || intPeriodEndMs === undefined) {
    throw new Error(`Invalid Scheduler period for time zone '${timezone}'.`);
  }
  if (intPeriodEndMs <= intPeriodStartMs) {
    throw new Error("Scheduler period end must be later than its start.");
  }

  return { intPeriodStartMs, intPeriodEndMs };
}

export const useSettingStore = defineStore("setting", {
  state: () => {
    return {
      theme: "light" as "light" | "dark",
      // theme: "dark",
      keepRdpSession: false as boolean,
      keepRdpSessionWidth: 1920 as number,
      keepRdpSessionHeight: 1080 as number,

      logTimeoutEnable: false as boolean,
      logTimeoutDays: 7 as number,
      videoTimeoutEnable: false as boolean,
      videoTimeoutDays: 7 as number,
      videoSizeEnable: false as boolean,
      videoSizeGB: 10 as number,

      projectLogFolderPath: "" as string,

      timezone: getSystemTimezone(),
    };
  },
  getters: {},
  actions: {
    initializeSetting(dictConfigExecutor: DictExecutorConfig): void {
      this.theme = dictConfigExecutor.theme;
      this.keepRdpSession = dictConfigExecutor.keepRdpSession;
      this.keepRdpSessionWidth = dictConfigExecutor.keepRdpSessionWidth;
      this.keepRdpSessionHeight = dictConfigExecutor.keepRdpSessionHeight;
      this.logTimeoutEnable = dictConfigExecutor.logTimeoutEnable;
      this.logTimeoutDays = dictConfigExecutor.logTimeoutDays;
      this.videoTimeoutEnable = dictConfigExecutor.videoTimeoutEnable;
      this.videoTimeoutDays = dictConfigExecutor.videoTimeoutDays;
      this.videoSizeEnable = dictConfigExecutor.videoSizeEnable;
      this.videoSizeGB = dictConfigExecutor.videoSizeGB;
      this.projectLogFolderPath = dictConfigExecutor.projectLogFolderPath;
      this.timezone = dictConfigExecutor.timezone;
    },

    async selectNewProjectLogFolderPath(): Promise<void> {
      const result = await invokeMain<string | null>(
        "invoke:select-project-log-folder-path",
      );
      if (result !== null) {
        this.projectLogFolderPath = result;
      }
    },

    async handleDeleteOptions(): Promise<void> {
      // Check if there are logs or videos need to be deleted.

      if (!this.logTimeoutEnable && !this.videoTimeoutEnable && !this.videoSizeEnable) {
        loggerRenderer.debug("No log or video files need to be deleted.");
        return;
      }

      const intInterval = Math.round((Date.now() - intLastCleanupAtMs) / 1000 / 60);
      loggerRenderer.debug(`Since last delete: ${intInterval} minutes.`);

      if (intInterval < 60) {
        return;
      }

      intLastCleanupAtMs = Date.now();

      if (this.logTimeoutEnable) {
        await invokeMain<void>("invoke:logCleanFolderByTimeout", this.logTimeoutDays);
      }
      if (this.videoTimeoutEnable) {
        await invokeMain<void>("invoke:logCleanVideoByTimeout", this.videoTimeoutDays);
      }
      if (this.videoSizeEnable) {
        await invokeMain<void>("invoke:logCleanVideoBySize", this.videoSizeGB);
      }
    },
  },
});

export const useInformationStore = defineStore("information", {
  state: () => {
    return {
      information: "..." as string,
      showAlert: false,
      tab: "Project Local Package" as
        | "Project Local Package"
        | "Task Scheduler"
        | "Task Queue"
        | "Task History"
        | "Setting",
    };
  },
  getters: {},
  actions: {
    showAlertMessage(message: string): void {
      loggerRenderer.error(message);
      this.information = message;
      this.showAlert = true;
    },
  },
});

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
      arrBindScheduler: [] as { title: string }[],
    };
  },
  getters: {},
  actions: {
    async loadPythonEnvironmentNames(): Promise<void> {
      this.arrPythonEnvironmentName = await invokeMain<string[]>(
        "invoke:getPythonEnvironmentNames",
      );
    },

    async dbSelectProjectNames(): Promise<void> {
      // Only run it if it's the first swtich to Project Local Package tab, or the data indeed needs to refresh.
      if (this.arrName.length === 0) {
        this.resetVersionAndDetail();

        const arrRows = await invokeMain<{ name: string }[]>("invoke:dbSelectProjectNames");
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

    async dbSelectProjectVersions(name: string): Promise<void> {
      this.resetVersionAndDetail();

      const arrRows = await invokeMain<{ version: string }[]>(
        "invoke:dbSelectProjectVersions",
        name,
      );
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

    async dbSelectProjectDetail(name: string, version: string): Promise<void> {
      this.resetDetail();
      await this.loadPythonEnvironmentNames();
      const dictRow = await invokeMain<DictColumns_Project_Detail_DB | undefined>(
        "invoke:dbSelectProjectDetail",
        { name, version },
      );
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

    async dbUpdateProjectDetail(): Promise<void> {
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
        await invokeMain<void>("invoke:dbUpdateProjectDetail", dictTemp);
        // Then the vue file will refresh project detail due to the name, version variables are managed by it.
      }
    },

    async dbSelectProjectBindSchedulers(): Promise<void> {
      if (this.dictDetail_edit !== undefined) {
        const arrRows = await invokeMain<{ name: string }[]>(
          "invoke:dbSelectProjectBindSchedulers",
          this.dictDetail_edit.id,
        );
        this.arrBindScheduler = arrRows.map((row) => {
          const dictTemp = {
            title: row.name,
          };
          return dictTemp;
        });
      }
    },

    async dbDeleteProject(): Promise<void> {
      if (this.dictDetail_edit !== undefined) {
        loggerRenderer.info(
          `Delete project: ${this.dictDetail_edit.id}-${this.dictDetail_edit.name}-${this.dictDetail_edit.version}`,
        );
        await invokeMain<void>("invoke:dbDeleteProject", this.dictDetail_edit.id);

        await invokeMain<void>("invoke:fileDeleteExecutorPackage", {
          name: this.dictDetail_edit.name,
          version: this.dictDetail_edit.version,
        });

        // Update the list.
        this.arrName = [];
        await this.dbSelectProjectNames();
        this.showDialog_delete = false;
        this.arrBindScheduler = [];
      }
    },
  },
});

export const useSchedulerStore = defineStore("scheduler", {
  state: () => {
    return {
      arrListItem: [] as DictColumns_Scheduler_ListItem[],

      // Edit and New use the same dialog size.
      showDialog_edit_new: false as boolean,
      isEditing: undefined as undefined | "edit" | "new",
      dictDetail_edit: undefined as DictColumns_Scheduler_Detail | undefined,
      detailCache_edit: undefined as string | undefined,

      showDialog_delete: false as boolean,
      dictDetail_new: undefined as DictColumns_Scheduler_Detail_BeforeInsert | undefined,
    };
  },
  getters: {},
  actions: {
    async dbSelectSchedulerList(): Promise<void> {
      if (this.arrListItem.length === 0) {
        const arrRow = await invokeMain<DictColumns_Scheduler_ListItem_DB[]>(
          "invoke:dbSelectSchedulerList",
        );

        this.arrListItem = arrRow.map((dictRow) => {
          return {
            name: dictRow.name,
            project_source: dictRow.project_source,
            project_name: dictRow.project_name,
            project_version: dictRow.project_version,
            cron: dictRow.cron,
            enable: dictRow.enable === 1,
            period_start_ms: dictRow.period_start_ms,
            period_end_ms: dictRow.period_end_ms,
            when_others_running: dictRow.when_others_running,
          };
        });
      }

      const queueStore = useQueueStore();
      queueStore.updateStrategyWhenOthersRunning();
      queueStore.resetPendingItem();
      queueStore.refreshListItem();
    },

    async refreshSchedulerList(): Promise<void> {
      this.arrListItem = [];
      await this.dbSelectSchedulerList();
      this.showDialog_edit_new = false;
      this.showDialog_delete = false;
    },

    async dbSelectSchedulerDetail(name: string): Promise<void> {
      const dictRow = await invokeMain<DictColumns_Scheduler_Detail_DB | undefined>(
        "invoke:dbSelectSchedulerDetail",
        name,
      );
      if (dictRow === undefined) {
        throw new Error(`Task Scheduler not found: ${name}`);
      }

      const settingStore = useSettingStore();
      this.dictDetail_edit = {
        id: dictRow.id,
        name: dictRow.name,
        project_source: dictRow.project_source,
        project_id: dictRow.project_id,
        project_name: dictRow.project_name,
        project_version: dictRow.project_version,
        python_environment_name: dictRow.python_environment_name,
        cron: dictRow.cron,
        when_others_running: dictRow.when_others_running,
        period_start: formatTimestampForDateTimeLocal(
          dictRow.period_start_ms,
          settingStore.timezone,
        ),
        period_end: formatTimestampForDateTimeLocal(
          dictRow.period_end_ms,
          settingStore.timezone,
        ),
        enable: dictRow.enable === 1,
        timeout_min: dictRow.timeout_min,
        builtin_log_level: dictRow.builtin_log_level,
        builtin_record_video: dictRow.builtin_record_video === 1,
        builtin_stop_shortcut: dictRow.builtin_stop_shortcut === 1,
        builtin_highlight_ui: dictRow.builtin_highlight_ui === 1,
        custom_prj_args: dictRow.custom_prj_args ? JSON.parse(dictRow.custom_prj_args) : [],
        created_at_ms: dictRow.created_at_ms,
        updated_at_ms: dictRow.updated_at_ms,
      };
      this.detailCache_edit = JSON.stringify(this.dictDetail_edit);
    },

    async dbInsertSchedulerDetail(): Promise<void> {
      if (
        this.dictDetail_new === undefined ||
        this.dictDetail_new.project_id === undefined
      ) {
        return;
      }

      const settingStore = useSettingStore();
      const { intPeriodStartMs, intPeriodEndMs } = getSchedulerPeriodTimestamps({
        periodStart: this.dictDetail_new.period_start,
        periodEnd: this.dictDetail_new.period_end,
        timezone: settingStore.timezone,
      });
      const dictTemp: DictColumns_Scheduler_Detail_ToInsert = {
        name: this.dictDetail_new.name,
        project_source: this.dictDetail_new.project_source,
        project_id: this.dictDetail_new.project_id,
        cron: this.dictDetail_new.cron,
        when_others_running: this.dictDetail_new.when_others_running,
        period_start_ms: intPeriodStartMs,
        period_end_ms: intPeriodEndMs,
        enable: this.dictDetail_new.enable ? 1 : 0,
        timeout_min: this.dictDetail_new.timeout_min,
        builtin_log_level: this.dictDetail_new.builtin_log_level,
        builtin_record_video: this.dictDetail_new.builtin_record_video ? 1 : 0,
        builtin_stop_shortcut: this.dictDetail_new.builtin_stop_shortcut ? 1 : 0,
        builtin_highlight_ui: this.dictDetail_new.builtin_highlight_ui ? 1 : 0,
        custom_prj_args: JSON.stringify(this.dictDetail_new.custom_prj_args),
      };
      await invokeMain<void>("invoke:dbInsertSchedulerDetail", dictTemp);
      await this.refreshSchedulerList();
    },

    async dbUpdateSchedulerDetail(): Promise<void> {
      if (this.dictDetail_edit === undefined) {
        return;
      }

      const settingStore = useSettingStore();
      const { intPeriodStartMs, intPeriodEndMs } = getSchedulerPeriodTimestamps({
        periodStart: this.dictDetail_edit.period_start,
        periodEnd: this.dictDetail_edit.period_end,
        timezone: settingStore.timezone,
      });
      const dictTemp: DictColumns_Scheduler_Detail_ToUpdate = {
        id: this.dictDetail_edit.id,
        name: this.dictDetail_edit.name,
        project_source: this.dictDetail_edit.project_source,
        project_id: this.dictDetail_edit.project_id,
        cron: this.dictDetail_edit.cron,
        when_others_running: this.dictDetail_edit.when_others_running,
        period_start_ms: intPeriodStartMs,
        period_end_ms: intPeriodEndMs,
        enable: this.dictDetail_edit.enable ? 1 : 0,
        timeout_min: this.dictDetail_edit.timeout_min,
        builtin_log_level: this.dictDetail_edit.builtin_log_level,
        builtin_record_video: this.dictDetail_edit.builtin_record_video ? 1 : 0,
        builtin_stop_shortcut: this.dictDetail_edit.builtin_stop_shortcut ? 1 : 0,
        builtin_highlight_ui: this.dictDetail_edit.builtin_highlight_ui ? 1 : 0,
        custom_prj_args: JSON.stringify(this.dictDetail_edit.custom_prj_args),
      };
      await invokeMain<void>("invoke:dbUpdateSchedulerDetail", dictTemp);
      await this.refreshSchedulerList();
    },

    async dbDeleteScheduler(): Promise<void> {
      if (this.dictDetail_edit === undefined) {
        return;
      }

      loggerRenderer.info(
        `Delete task scheduler: ${this.dictDetail_edit.id}-${this.dictDetail_edit.name}`,
      );
      await invokeMain<void>("invoke:dbDeleteScheduler", this.dictDetail_edit.id);
      await this.refreshSchedulerList();
    },
  },
});

export const useQueueStore = defineStore("queue", {
  state: () => {
    return {
      arrListItem: [] as Dict_TaskQueue_ListItem[],
      arrWaitingItem: [] as Dict_TaskQueue_ListItem[],

      dictStrategyWhenOtherRunning: {} as Record<string, "cancel" | "wait" | "run">,
      arrPendingItem: [] as Dict_TaskQueue_ListItem[],

      isChecking: false as boolean,
    };
  },
  getters: {},
  actions: {
    resetPendingItem(): void {
      const arrPendingItem: Dict_TaskQueue_ListItem[] = [];
      const intNowMs = Date.now();
      const schedulerStore = useSchedulerStore();
      const settingStore = useSettingStore();

      for (const dictScheduler of schedulerStore.arrListItem) {
        if (!dictScheduler.enable) {
          continue;
        }

        try {
          const intCurrentDateMs = Math.max(intNowMs, dictScheduler.period_start_ms - 1);
          const intervalObj = CronExpressionParser.parse(dictScheduler.cron, {
            currentDate: new Date(intCurrentDateMs),
            endDate: new Date(dictScheduler.period_end_ms),
            tz: settingStore.timezone,
          });

          arrPendingItem.push({
            name: dictScheduler.name,
            project_source: dictScheduler.project_source,
            project_name: dictScheduler.project_name,
            project_version: dictScheduler.project_version,
            estimated_run_at_ms: intervalObj.next().toDate().getTime(),
            waiting: false,
          });
        } catch (e: unknown) {
          const strMessage = e instanceof Error ? e.message : String(e);
          loggerRenderer.debug(
            `No pending run is available for Scheduler '${dictScheduler.name}': ${strMessage}`,
          );
        }
      }

      arrPendingItem.sort(
        (dictLeft, dictRight) =>
          dictLeft.estimated_run_at_ms - dictRight.estimated_run_at_ms,
      );
      this.arrPendingItem = arrPendingItem;
    },

    async checkWhetherRun_PendingItem(): Promise<void> {
      if (this.isChecking) {
        return;
      }

      this.isChecking = true;
      let boolNeedsRefresh = false;

      try {
        const intNowMs = Date.now();
        let boolOthersRunning = await this.checkOthersRunning_BeforeLoop();

        // Loop from the end so due entries can be removed in place.
        for (let index = this.arrPendingItem.length - 1; index >= 0; index--) {
          const dictQueueItem = this.arrPendingItem[index];
          if (dictQueueItem.estimated_run_at_ms > intNowMs) {
            continue;
          }

          const strStrategy =
            this.dictStrategyWhenOtherRunning[dictQueueItem.name] ?? "cancel";
          loggerRenderer.info(
            `Time to run task: ${dictQueueItem.name}, when_others_running: ${strStrategy}`,
          );

          if (!boolOthersRunning || strStrategy === "run") {
            loggerRenderer.info(
              boolOthersRunning
                ? "Run the task."
                : "Have no other task running, run the task.",
            );
            await this.runTask(dictQueueItem.name);
            boolOthersRunning = true;
            this.arrPendingItem.splice(index, 1);
            boolNeedsRefresh = true;
            continue;
          }

          if (strStrategy === "wait") {
            loggerRenderer.info("Move the task into the waiting queue.");
            dictQueueItem.waiting = true;
            this.arrWaitingItem.push(dictQueueItem);
          } else {
            loggerRenderer.info("Cancel the task because another task is running.");
          }

          this.arrPendingItem.splice(index, 1);
          boolNeedsRefresh = true;
        }

        if (boolNeedsRefresh) {
          this.resetPendingItem();
          this.refreshListItem();
        }
      } finally {
        this.isChecking = false;
      }
    },

    async checkWhetherRun_WaitingItem(): Promise<void> {
      const boolOthersRunning = await this.checkOthersRunning_BeforeLoop();
      if (boolOthersRunning || this.arrWaitingItem.length === 0) {
        return;
      }

      loggerRenderer.info("Run a waiting task.");
      await this.runTask(this.arrWaitingItem[0].name);
      this.arrWaitingItem.splice(0, 1);
      this.refreshListItem();
    },

    async checkOthersRunning_BeforeLoop(): Promise<boolean> {
      const historyStore = useHistoryStore();
      const boolOthersRunning = await historyStore.dbSelectCountHistoryRunning();
      loggerRenderer.debug(`Other tasks running: ${boolOthersRunning}`);
      return boolOthersRunning;
    },

    async runTask(name: string): Promise<void> {
      const schedulerStore = useSchedulerStore();
      await schedulerStore.dbSelectSchedulerDetail(name);

      if (schedulerStore.dictDetail_edit === undefined) {
        throw new Error(`Failed to load Task Scheduler: ${name}`);
      }

      const dictTemp: DictColumns_Project_Detail_Run = {
        scheduler_name: schedulerStore.dictDetail_edit.name,
        project_source: schedulerStore.dictDetail_edit.project_source,
        id: schedulerStore.dictDetail_edit.project_id,
        name: schedulerStore.dictDetail_edit.project_name,
        version: schedulerStore.dictDetail_edit.project_version,
        python_environment_name: schedulerStore.dictDetail_edit.python_environment_name,
        timeout_min: schedulerStore.dictDetail_edit.timeout_min,
        builtin_log_level: schedulerStore.dictDetail_edit.builtin_log_level,
        builtin_record_video: schedulerStore.dictDetail_edit.builtin_record_video,
        builtin_stop_shortcut: schedulerStore.dictDetail_edit.builtin_stop_shortcut,
        builtin_highlight_ui: schedulerStore.dictDetail_edit.builtin_highlight_ui,
        custom_prj_args: schedulerStore.dictDetail_edit.custom_prj_args,
      };
      await invokeMain<void>("invoke:pythonRun", sanitizeJsonObj(dictTemp));

      const historyStore = useHistoryStore();
      await historyStore.refreshHistoryList();
    },

    updateStrategyWhenOthersRunning(): void {
      const schedulerStore = useSchedulerStore();
      const dictStrategy: Record<string, "cancel" | "wait" | "run"> = {};

      for (const dictScheduler of schedulerStore.arrListItem) {
        dictStrategy[dictScheduler.name] = dictScheduler.when_others_running;
      }

      this.dictStrategyWhenOtherRunning = dictStrategy;
    },

    refreshListItem(): void {
      this.arrListItem = [...this.arrWaitingItem, ...this.arrPendingItem];
      loggerRenderer.debug("Refresh Queue List.");
    },
  },
});

export const useHistoryStore = defineStore("history", {
  state: () => {
    return {
      arrListItem: [] as DictColumns_History_ListItem_DB[],
      itemLength: 0 as number,
      dictOptionsCache: undefined as Dict_History_Options | undefined,

      filterSchedulerName: "" as string,
      filterSource: null as "local" | "console" | null,
      filterProjectName: "" as string,
      filterProjectVersion: "" as string,
      filterStatus: null as TypeTaskHistoryStatus | null,
    };
  },
  getters: {},
  actions: {
    async dbSelectLimitHistoryList(
      options: Dict_History_Options_Component | null,
    ): Promise<void> {
      if (options) {
        // Make sure this.dictOptionsCache not use a same object(memory address) with v-data-table-server's options. Otherwise the page button may not work.

        const dictTemp: Dict_History_Options_Component = sanitizeJsonObj(options);

        this.dictOptionsCache = {
          page: dictTemp.page,
          itemsPerPage: dictTemp.itemsPerPage,
          sortBy: dictTemp.sortBy,
          // dictTemp.search is a string, deserialize it.
          search: JSON.parse(dictTemp.search) as Dict_History_Search,
        };
      }

      // If dictOptionsCache is not undefined, means user has clicked Task History, can use the dictOptionsCache to upload data. Otherwise didn't need to refresh.
      if (!this.dictOptionsCache) {
        loggerRenderer.debug("Task History never clicked, not updated data.");
        return;
      }

      const result = await invokeMain<DictColumns_History_ListItem_Limit_DB>(
        "invoke:dbSelectLimitHistoryList",
        sanitizeJsonObj(this.dictOptionsCache),
      );
      // loggerRenderer.debug(JSON.stringify(result, null, 2));
      this.arrListItem = result.rows;
      this.itemLength = result.total;
    },

    async refreshHistoryList(): Promise<void> {
      await this.dbSelectLimitHistoryList(null);
    },

    async dbSelectCountHistoryRunning(): Promise<boolean> {
      return await invokeMain<boolean>("invoke:dbSelectCountHistoryRunning");
    },
  },
});
