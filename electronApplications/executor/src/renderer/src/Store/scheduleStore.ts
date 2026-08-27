// FileName: scheduleStore.ts

import { defineStore } from "pinia";

import { invokeMain } from "../IPC/ipc";
import { loggerRenderer } from "../Logging/logger";
import {
  formatTimestampForDateTimeLocal,
  parseDateTimeLocalToTimestamp,
} from "../Common/time";
import type { Dict_Detail_NewScheduleForm, Dict_Detail_ScheduleForm_All } from "../Schedule/types";
import { useSettingStore } from "./settingStore";
import type {
  Dict_ScheduleCreate,
  Dict_ListItem_Schedule,
  Dict_ScheduleUpdate,
} from "../../../shared/schedule";

function getSchedulePeriodTimestamps({
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
    throw new Error(`Invalid Schedule period for time zone '${timezone}'.`);
  }
  if (intPeriodEndMs <= intPeriodStartMs) {
    throw new Error("Schedule period end must be later than its start.");
  }

  return { intPeriodStartMs, intPeriodEndMs };
}

export const useScheduleStore = defineStore("schedule", {
  state: () => {
    return {
      arrListItem: [] as Dict_ListItem_Schedule[],
      arrProjectName: [] as string[],
      arrProjectVersion: [] as string[],

      // Edit and New use the same dialog size.
      showFormDialog: false as boolean,
      formMode: undefined as undefined | "edit" | "new",
      dictDetailEdit: undefined as Dict_Detail_ScheduleForm_All | undefined,
      strDetailCacheEdit: undefined as string | undefined,

      showDeleteDialog: false as boolean,
      dictDetailNew: undefined as Dict_Detail_NewScheduleForm | undefined,
    };
  },
  actions: {
    async loadProjectNames(): Promise<void> {
      this.arrProjectName = (await invokeMain("getProjectNames")).map((row) => row.name);
    },

    async fetchProjectVersions(projectName: string): Promise<string[]> {
      return (await invokeMain("getProjectVersions", projectName)).map(
        (row) => row.version,
      );
    },

    setProjectVersions(arrVersion: string[]): void {
      this.arrProjectVersion = arrVersion;
    },

    resetProjectVersions(): void {
      this.arrProjectVersion = [];
    },

    async loadScheduleList(): Promise<void> {
      if (this.arrListItem.length === 0) {
        this.arrListItem = await invokeMain("getScheduleList");
      }
    },

    async refreshScheduleList(): Promise<void> {
      this.arrListItem = [];
      await this.loadScheduleList();
      this.showFormDialog = false;
      this.showDeleteDialog = false;
      this.formMode = undefined;
      this.dictDetailNew = undefined;
      this.dictDetailEdit = undefined;
      this.strDetailCacheEdit = undefined;
    },

    async loadScheduleDetail(scheduleName: string): Promise<void> {
      const dictDetail = await invokeMain("getScheduleDetail", scheduleName);
      if (dictDetail === undefined) {
        throw new Error(`Schedule not found: ${scheduleName}`);
      }

      const settingStore = useSettingStore();
      const { period_start_ms, period_end_ms, ...dictDetailWithoutPeriod } = dictDetail;
      this.dictDetailEdit = {
        ...dictDetailWithoutPeriod,
        period_start: formatTimestampForDateTimeLocal(
          period_start_ms,
          settingStore.timezone,
        ),
        period_end: formatTimestampForDateTimeLocal(period_end_ms, settingStore.timezone),
      };
      this.strDetailCacheEdit = JSON.stringify(this.dictDetailEdit);
    },

    async createSchedule(): Promise<void> {
      if (this.dictDetailNew === undefined || this.dictDetailNew.project_id === undefined) {
        return;
      }

      const settingStore = useSettingStore();
      const { intPeriodStartMs, intPeriodEndMs } = getSchedulePeriodTimestamps({
        periodStart: this.dictDetailNew.period_start,
        periodEnd: this.dictDetailNew.period_end,
        timezone: settingStore.timezone,
      });
      const dictTemp: Dict_ScheduleCreate = {
        name: this.dictDetailNew.name,
        project_id: this.dictDetailNew.project_id,
        cron: this.dictDetailNew.cron,
        run_conflict_policy: this.dictDetailNew.run_conflict_policy,
        period_start_ms: intPeriodStartMs,
        period_end_ms: intPeriodEndMs,
        enable: this.dictDetailNew.enable,
        timeout_min: this.dictDetailNew.timeout_min,
        builtin_log_level: this.dictDetailNew.builtin_log_level,
        builtin_record_video: this.dictDetailNew.builtin_record_video,
        builtin_stop_shortcut: this.dictDetailNew.builtin_stop_shortcut,
        builtin_highlight_ui: this.dictDetailNew.builtin_highlight_ui,
        custom_prj_args: this.dictDetailNew.custom_prj_args,
      };
      await invokeMain("createSchedule", dictTemp);
      await this.refreshScheduleList();
    },

    async saveSchedule(): Promise<void> {
      if (
        this.dictDetailEdit === undefined ||
        this.dictDetailEdit.project_id === undefined
      ) {
        return;
      }

      const settingStore = useSettingStore();
      const { intPeriodStartMs, intPeriodEndMs } = getSchedulePeriodTimestamps({
        periodStart: this.dictDetailEdit.period_start,
        periodEnd: this.dictDetailEdit.period_end,
        timezone: settingStore.timezone,
      });
      const dictTemp: Dict_ScheduleUpdate = {
        id: this.dictDetailEdit.id,
        name: this.dictDetailEdit.name,
        project_id: this.dictDetailEdit.project_id,
        cron: this.dictDetailEdit.cron,
        run_conflict_policy: this.dictDetailEdit.run_conflict_policy,
        period_start_ms: intPeriodStartMs,
        period_end_ms: intPeriodEndMs,
        enable: this.dictDetailEdit.enable,
        timeout_min: this.dictDetailEdit.timeout_min,
        builtin_log_level: this.dictDetailEdit.builtin_log_level,
        builtin_record_video: this.dictDetailEdit.builtin_record_video,
        builtin_stop_shortcut: this.dictDetailEdit.builtin_stop_shortcut,
        builtin_highlight_ui: this.dictDetailEdit.builtin_highlight_ui,
        custom_prj_args: this.dictDetailEdit.custom_prj_args,
      };
      await invokeMain("saveSchedule", dictTemp);
      await this.refreshScheduleList();
    },

    async deleteSchedule(): Promise<void> {
      if (this.dictDetailEdit === undefined) {
        return;
      }

      loggerRenderer.info(
        `Delete schedule: ${this.dictDetailEdit.id}-${this.dictDetailEdit.name}`,
      );
      await invokeMain("deleteSchedule", this.dictDetailEdit.id);
      await this.refreshScheduleList();
    },
  },
});
