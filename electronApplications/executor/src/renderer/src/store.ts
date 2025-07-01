// FileName: store.ts
import { defineStore } from "pinia";
import { CronExpressionParser } from "cron-parser";
import moment from "moment";

import { loggerRenderer, invokeMain } from "./ipcOfRenderer";
import { sanitizeJsonObj } from "./commonFunc";
import {
  DictExecutorConfig,
  DictColumns_Project_Detail_DB,
  DictColumns_Project_Detail,
  DictColumns_Project_Detail_ToInsert,
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
} from "../../shared/interface";

let datetimeLastDelete: number = new Date().getTime();

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

      timezone: "" as string,
    };
  },
  getters: {},
  actions: {
    initializeSetting(dictConfigExecutor: DictExecutorConfig): void {
      this.theme = dictConfigExecutor["theme"];
      this.keepRdpSession = dictConfigExecutor["keepRdpSession"];
      this.keepRdpSessionWidth = dictConfigExecutor["keepRdpSessionWidth"];
      this.keepRdpSessionHeight = dictConfigExecutor["keepRdpSessionHeight"];
      this.logTimeoutEnable = dictConfigExecutor["logTimeoutEnable"];
      this.logTimeoutDays = dictConfigExecutor["logTimeoutDays"];
      this.videoTimeoutEnable = dictConfigExecutor["videoTimeoutEnable"];
      this.videoTimeoutDays = dictConfigExecutor["videoTimeoutDays"];
      this.videoSizeEnable = dictConfigExecutor["videoSizeEnable"];
      this.videoSizeGB = dictConfigExecutor["videoSizeGB"];
      this.projectLogFolderPath = dictConfigExecutor["projectLogFolderPath"];
      this.timezone = dictConfigExecutor["timezone"];
    },

    async selectNewProjectLogFolderPath(): Promise<void> {
      const result: string | null = await invokeMain(
        "invoke:select-project-log-folder-path"
      );
      if (result) {
        this.projectLogFolderPath = result;
      }
    },

    async handleDeleteOptions(): Promise<void> {
      // Check if there are logs or videos need to be deleted.

      if (!this.logTimeoutEnable && !this.videoTimeoutEnable && !this.videoSizeEnable) {
        loggerRenderer.debug("Not need to delete log and video files.");
        return;
      }

      const intInterval = Math.round(
        (new Date().getTime() - datetimeLastDelete) / 1000 / 60
      );
      loggerRenderer.debug(`Since last delete: ${intInterval} minutes.`);

      if (intInterval < 60) {
        return;
      }

      datetimeLastDelete = new Date().getTime();

      if (this.logTimeoutEnable) {
        await invokeMain("invoke:logCleanFolderByTimeout", this.logTimeoutDays);
      }
      if (this.videoTimeoutEnable) {
        await invokeMain("invoke:logCleanVideoByTimeout", this.videoTimeoutDays);
      }
      if (this.videoSizeEnable) {
        await invokeMain("invoke:logCleanVideoBySize", this.videoSizeGB);
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
    async dbSelectProjectNames(): Promise<void> {
      // Only run it if it's the first swtich to Project Local Package tab, or the data indeed needs to refresh.
      if (this.arrName.length === 0) {
        this.resetVersionAndDetail();

        const arrRows: { name: string }[] = await invokeMain("invoke:dbSelectProjectNames");
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

      const arrRows: { version: string }[] = await invokeMain(
        "invoke:dbSelectProjectVersions",
        name
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
      const dictRow: DictColumns_Project_Detail_DB = await invokeMain(
        "invoke:dbSelectProjectDetail",
        {
          name,
          version,
        }
      );

      // Initialize Details:
      this.dictDetail_edit = {
        id: dictRow.id,
        name: dictRow.name,
        version: dictRow.version,
        description: dictRow.description,
        timeout_min: dictRow.timeout_min,
        buildin_log_level: dictRow.buildin_log_level,
        buildin_record_video: dictRow.buildin_record_video === 1,
        buildin_stop_shortcut: dictRow.buildin_stop_shortcut === 1,
        buildin_highlight_ui: dictRow.buildin_highlight_ui === 1,
        custom_prj_args: dictRow.custom_prj_args ? JSON.parse(dictRow.custom_prj_args) : [],
        created_at: dictRow.created_at,
        updated_at: dictRow.updated_at,
      };
      // loggerRenderer.debug(JSON.stringify(this.dictDetail, null, 2));
      this.detailCache_edit = JSON.stringify(this.dictDetail_edit);
    },

    async dbInsertProjectDetail(
      dictDetail: DictColumns_Project_Detail_ToInsert
    ): Promise<void> {
      await invokeMain("invoke:dbInsertProjectDetail", dictDetail);
      this.arrName = [];
      await this.dbSelectProjectNames();
    },

    async dbUpdateProjectDetail(): Promise<void> {
      if (this.dictDetail_edit) {
        const dictTemp: DictColumns_Project_Detail_ToUpdate = {
          id: this.dictDetail_edit.id,
          name: this.dictDetail_edit.name,
          version: this.dictDetail_edit.version,
          description: this.dictDetail_edit.description,
          timeout_min: this.dictDetail_edit.timeout_min,
          buildin_log_level: this.dictDetail_edit.buildin_log_level,
          buildin_record_video: this.dictDetail_edit.buildin_record_video ? 1 : 0,
          buildin_stop_shortcut: this.dictDetail_edit.buildin_stop_shortcut ? 1 : 0,
          buildin_highlight_ui: this.dictDetail_edit.buildin_highlight_ui ? 1 : 0,
          custom_prj_args: JSON.stringify(this.dictDetail_edit.custom_prj_args),
        };
        await invokeMain("invoke:dbUpdateProjectDetail", dictTemp);
        // Then the vue file will refresh project detail due to the name, version variables are managed by it.
      }
    },

    async dbSelectProjectBindSchedulers(): Promise<void> {
      if (this.dictDetail_edit) {
        const arrRows: { name: string }[] = await invokeMain(
          "invoke:dbSelectProjectBindSchedulers",
          this.dictDetail_edit.id
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
      if (this.dictDetail_edit) {
        loggerRenderer.info(
          `Delete project: ${this.dictDetail_edit.id}-${this.dictDetail_edit.name}-${this.dictDetail_edit.version}`
        );
        await invokeMain("invoke:dbDeleteProject", this.dictDetail_edit.id);

        await invokeMain("invoke:fileDeleteExecutorPackage", {
          name: this.dictDetail_edit.name,
          version: this.dictDetail_edit.version,
        });

        // Update the list.
        this.arrName = [];
        await this.dbSelectProjectNames();
        this.showDialog_delete = false;
        this.arrBindScheduler = [];

        // Update scheduler list because some bound data show be null.
        const schedulerStore = useSchedulerStore();
        schedulerStore.arrListItem = [];
        await schedulerStore.dbSelectSchedulerList();
      }
    },
  },
});

export const useSchedulerStore = defineStore("scheduler", {
  state: () => {
    return {
      arrListItem: [] as DictColumns_Scheduler_ListItem[],

      // edit and new card use a same size dialog.
      showDialog_edit_new: false as boolean,
      isEditing: undefined as undefined | "edit" | "new",
      dictDetail_edit: undefined as DictColumns_Scheduler_Detail | undefined,
      detailCache_edit: undefined as string | undefined,

      // delete use another dialog.
      showDialog_delete: false as boolean,
      dictDetail_new: undefined as DictColumns_Scheduler_Detail_BeforeInsert | undefined,
    };
  },
  getters: {},
  actions: {
    async dbSelectSchedulerList(): Promise<void> {
      // Only run it if it's the first swtich to Task Scheduler tab, or the data indeed needs to refresh.
      if (this.arrListItem.length === 0) {
        const arrRows: DictColumns_Scheduler_ListItem_DB[] = await invokeMain(
          "invoke:dbSelectSchedulerList"
        );
        this.arrListItem = arrRows.map((row) => {
          const dictTemp: DictColumns_Scheduler_ListItem = {
            name: row.name,
            project_source: row.project_source,
            project_name: row.project_name,
            project_version: row.project_version,
            cron: row.cron,
            enable: row.enable === 1,
            period_start: row.period_start,
            period_end: row.period_end,
            when_others_running: row.when_others_running,
          };
          return dictTemp;
        });
        // loggerRenderer.debug(JSON.stringify(this.arrListItem, null, 2));
      }

      /* Update data of queueStore. */
      const queueStore = useQueueStore();
      queueStore.updateStrategyWhenOthersRunning();
      queueStore.ResetPendingItem();
      queueStore.refreshListItem();
    },

    async refreshSchedulerList(): Promise<void> {
      this.arrListItem = [];
      await this.dbSelectSchedulerList();
      this.showDialog_edit_new = false;
      this.showDialog_delete = false;
    },

    async dbSelectSchedulerDetail(name: string): Promise<void> {
      const dictRow: DictColumns_Scheduler_Detail_DB = await invokeMain(
        "invoke:dbSelectSchedulerDetail",
        name
      );

      this.dictDetail_edit = {
        id: dictRow.id,
        name: dictRow.name,
        project_source: dictRow.project_source,
        project_id: dictRow.project_id,
        project_name: dictRow.project_name,
        project_version: dictRow.project_version,
        cron: dictRow.cron,
        when_others_running: dictRow.when_others_running,
        period_start: dictRow.period_start,
        period_end: dictRow.period_end,
        enable: dictRow.enable === 1,
        timeout_min: dictRow.timeout_min,
        buildin_log_level: dictRow.buildin_log_level,
        buildin_record_video: dictRow.buildin_record_video === 1,
        buildin_stop_shortcut: dictRow.buildin_stop_shortcut === 1,
        buildin_highlight_ui: dictRow.buildin_highlight_ui === 1,
        custom_prj_args: dictRow.custom_prj_args ? JSON.parse(dictRow.custom_prj_args) : [],
        created_at: dictRow.created_at,
        updated_at: dictRow.updated_at,
      };
      loggerRenderer.debug(JSON.stringify(this.dictDetail_edit, null, 2));
      this.detailCache_edit = JSON.stringify(this.dictDetail_edit);
    },

    async dbInsertSchedulerDetail(): Promise<void> {
      if (this.dictDetail_new) {
        const dictTemp: DictColumns_Scheduler_Detail_ToInsert = {
          name: this.dictDetail_new.name,
          project_source: this.dictDetail_new.project_source,
          project_id: this.dictDetail_new.project_id as number,
          cron: this.dictDetail_new.cron,
          when_others_running: this.dictDetail_new.when_others_running,
          period_start: this.dictDetail_new.period_start,
          period_end: this.dictDetail_new.period_end,
          enable: this.dictDetail_new.enable ? 1 : 0,
          timeout_min: this.dictDetail_new.timeout_min,
          buildin_log_level: this.dictDetail_new.buildin_log_level,
          buildin_record_video: this.dictDetail_new.buildin_record_video ? 1 : 0,
          buildin_stop_shortcut: this.dictDetail_new.buildin_stop_shortcut ? 1 : 0,
          buildin_highlight_ui: this.dictDetail_new.buildin_highlight_ui ? 1 : 0,
          custom_prj_args: JSON.stringify(this.dictDetail_new.custom_prj_args),
        };
        await invokeMain("invoke:dbInsertSchedulerDetail", dictTemp);

        this.refreshSchedulerList();
      }
    },

    async dbUpdateSchedulerDetail(): Promise<void> {
      if (this.dictDetail_edit) {
        // Save data into database and then close the dialog.
        const dictTemp: DictColumns_Scheduler_Detail_ToUpdate = {
          id: this.dictDetail_edit.id,
          name: this.dictDetail_edit.name,
          project_source: this.dictDetail_edit.project_source,
          project_id: this.dictDetail_edit.project_id,
          cron: this.dictDetail_edit.cron,
          when_others_running: this.dictDetail_edit.when_others_running,
          period_start: this.dictDetail_edit.period_start,
          period_end: this.dictDetail_edit.period_end,
          enable: this.dictDetail_edit.enable ? 1 : 0,
          timeout_min: this.dictDetail_edit.timeout_min,
          buildin_log_level: this.dictDetail_edit.buildin_log_level,
          buildin_record_video: this.dictDetail_edit.buildin_record_video ? 1 : 0,
          buildin_stop_shortcut: this.dictDetail_edit.buildin_stop_shortcut ? 1 : 0,
          buildin_highlight_ui: this.dictDetail_edit.buildin_highlight_ui ? 1 : 0,
          custom_prj_args: JSON.stringify(this.dictDetail_edit.custom_prj_args),
        };
        await invokeMain("invoke:dbUpdateSchedulerDetail", dictTemp);

        this.refreshSchedulerList();
      }
    },

    async dbDeleteScheduler(): Promise<void> {
      if (this.dictDetail_edit) {
        loggerRenderer.info(
          `Delete task scheduler: ${this.dictDetail_edit.id}-${this.dictDetail_edit.name}`
        );
        await invokeMain("invoke:dbDeleteScheduler", this.dictDetail_edit.id);

        this.refreshSchedulerList();
      }
    },
  },
});

export const useQueueStore = defineStore("queue", {
  state: () => {
    return {
      arrListItem: [] as Dict_TaskQueue_ListItem[],
      arrWaitingItem: [] as Dict_TaskQueue_ListItem[],

      dictStrategyWhenOtherRunning: {} as {
        [key: string]: "cancel" | "wait" | "run";
      },
      arrPendingItem: [] as Dict_TaskQueue_ListItem[],

      isChecking: false as boolean,
    };
  },
  getters: {},
  actions: {
    ResetPendingItem(): void {
      // Reset arrListItem by schedulerStore.arrListItem data
      const arrTemp: Dict_TaskQueue_ListItem[] = [];
      const momentNow = moment(new Date());
      const schedulerStore = useSchedulerStore();

      for (let index = 0; index < schedulerStore.arrListItem.length; index++) {
        const item = schedulerStore.arrListItem[index];
        if (item.enable === false) {
          // It's not enabled, doesn't need to run.
          continue;
        }

        try {
          // Calculate the next run time. If current date is later than period_start, use the current date.
          const interval = CronExpressionParser.parse(item.cron, {
            currentDate: moment(item.period_start, "YYYY-MM-DD HH:mm:ss").isBefore(
              momentNow
            )
              ? momentNow.format("YYYY-MM-DD HH:mm:ss")
              : item.period_start,
            endDate: item.period_end,
          });

          const strEstimatedRunTime = moment(interval.next().toDate()).format(
            "YYYY-MM-DD HH:mm:ss"
          );
          // console.log(item.name + " - " + strEstimatedRunTime);

          const dictTemp: Dict_TaskQueue_ListItem = {
            name: item.name,
            project_source: item.project_source,
            project_name: item.project_name,
            project_version: item.project_version,
            estimated_run_time: strEstimatedRunTime,
            waiting: false,
          };

          arrTemp.push(dictTemp);
        } catch (e) {
          loggerRenderer.error((e as Error).message);
          continue;
        }
      }

      /* console.log(JSON.stringify(arrTemp, null, 2));
      console.log(
        "Sorted: ",
        arrTemp.sort((a, b) => a.estimated_run_time.localeCompare(b.estimated_run_time))
      ); */

      arrTemp.sort((a, b) => a.estimated_run_time.localeCompare(b.estimated_run_time));

      this.arrPendingItem = arrTemp;
    },

    async checkWhetherRun_PendingItem(): Promise<void> {
      if (this.isChecking) {
        return;
      }

      // Set the flag, if the previous check doesn't end in the interval, skip the new check.
      console.log(`Check Pending Start at ${new Date()}`);

      this.isChecking = true;
      let boolNeedsRefresh = false;

      /* The check starts. */

      const momentNow = moment(new Date());
      let boolOthersRunning = await this.checkOthersRunning_BeforeLoop();

      // Loop from end, to delete later.
      for (let index = this.arrPendingItem.length - 1; index >= 0; index--) {
        const item = this.arrPendingItem[index];
        if (!moment(item.estimated_run_time, "YYYY-MM-DD HH:mm:ss").isBefore(momentNow)) {
          // loggerRenderer.debug(`The task [${item.name}] has not reached the run time.`);
          continue;
        }

        loggerRenderer.info(
          `Time to run task: ${item.name}, when_others_running: ${
            this.dictStrategyWhenOtherRunning[item.name]
          }`
        );

        if (!boolOthersRunning) {
          loggerRenderer.info("Have no other task running, run the task.");

          await this.runTask(item.name);
          boolOthersRunning = true;

          this.arrPendingItem.splice(index, 1);
          boolNeedsRefresh = true;
          continue;
        }

        loggerRenderer.info("Some tasks are running.");

        // Other tasks are running, check "when_others_running"
        switch (this.dictStrategyWhenOtherRunning[item.name]) {
          case "run": {
            loggerRenderer.info("Run the task.");

            await this.runTask(item.name);
            boolOthersRunning = true;

            this.arrPendingItem.splice(index, 1);
            boolNeedsRefresh = true;
            continue;
          }

          case "wait": {
            loggerRenderer.info("Move the task into arrWaitingItem.");

            item.waiting = true;
            this.arrWaitingItem.push(item);

            this.arrPendingItem.splice(index, 1);
            boolNeedsRefresh = true;
            continue;
          }

          default: {
            // "cancel"
            loggerRenderer.info("Cancel the task.");

            this.arrPendingItem.splice(index, 1);
            boolNeedsRefresh = true;
            continue;
          }
        }
      }

      /* The check ends. */

      if (boolNeedsRefresh) {
        this.ResetPendingItem();
        this.refreshListItem();
      }

      // Reset the flag to make the next interval can work.
      this.isChecking = false;
    },

    async checkWhetherRun_WaitingItem(): Promise<void> {
      // When a task end, check whether has waiting task can be run.

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
      console.log(`Other tasks running: ${boolOthersRunning}`);
      return boolOthersRunning;
    },

    async runTask(name: string): Promise<void> {
      // Get data from schedulerStore.dictDetail_edit
      const schedulerStore = useSchedulerStore();
      await schedulerStore.dbSelectSchedulerDetail(name);

      if (schedulerStore.dictDetail_edit) {
        const dictTemp: DictColumns_Project_Detail_Run = {
          scheduler_name: schedulerStore.dictDetail_edit.name,
          // Only "local" now.
          project_source: schedulerStore.dictDetail_edit.project_source,
          id: schedulerStore.dictDetail_edit.project_id,
          name: schedulerStore.dictDetail_edit.project_name,
          version: schedulerStore.dictDetail_edit.project_version,
          timeout_min: schedulerStore.dictDetail_edit.timeout_min,
          buildin_log_level: schedulerStore.dictDetail_edit.buildin_log_level,
          buildin_record_video: schedulerStore.dictDetail_edit.buildin_record_video,
          buildin_stop_shortcut: schedulerStore.dictDetail_edit.buildin_stop_shortcut,
          buildin_highlight_ui: schedulerStore.dictDetail_edit.buildin_highlight_ui,
          custom_prj_args: schedulerStore.dictDetail_edit.custom_prj_args,
        };
        await invokeMain("invoke:pythonRun", sanitizeJsonObj(dictTemp));
        const historyStore = useHistoryStore();
        await historyStore.refreshHistoryList();
      } else {
        loggerRenderer.error("(!!!It should not appear.) Failure to get scheduler detail.");
      }
    },

    updateStrategyWhenOthersRunning(): void {
      const schedulerStore = useSchedulerStore();
      this.dictStrategyWhenOtherRunning = schedulerStore.arrListItem.reduce((acc, item) => {
        acc[item.name] = item.when_others_running;
        return acc;
      }, {});
    },

    refreshListItem(): void {
      this.arrListItem = [...this.arrWaitingItem, ...this.arrPendingItem];
      loggerRenderer.debug("Refrsh Queue List.");
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
      filterStatus: null as "running" | "completed" | "error" | "cancel" | "timeout" | null,
    };
  },
  getters: {},
  actions: {
    async dbSelectLimitHistoryList(
      options: Dict_History_Options_Component | null
    ): Promise<void> {
      console.log(options);
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

      console.log(JSON.stringify(this.dictOptionsCache, null, 2));

      const result = (await invokeMain(
        "invoke:dbSelectLimitHistoryList",
        sanitizeJsonObj(this.dictOptionsCache)
      )) as DictColumns_History_ListItem_Limit_DB;
      // loggerRenderer.debug(JSON.stringify(result, null, 2));
      this.arrListItem = result.rows;
      this.itemLength = result.total;
    },

    async refreshHistoryList(): Promise<void> {
      await this.dbSelectLimitHistoryList(null);
    },

    async dbSelectCountHistoryRunning(): Promise<boolean> {
      return (await invokeMain("invoke:dbSelectCountHistoryRunning")) as boolean;
    },
  },
});
