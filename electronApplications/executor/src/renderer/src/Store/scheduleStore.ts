import { defineStore } from "pinia";

import { invokeMain } from "../IPC/ipc";
import { loggerRenderer } from "../Logging/logger";
import {
  formatTimestampForDateTimeLocal,
  parseDateTimeLocalToTimestamp,
} from "../Common/time";
import type { DictNewScheduleFormDetail, DictScheduleFormDetail } from "../Schedule/types";
import { useSettingStore } from "./settingStore";
import type {
  DictScheduleCreate,
  DictScheduleListItem,
  DictScheduleUpdate,
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
      arrListItem: [] as DictScheduleListItem[],
      arrProjectName: [] as string[],
      arrProjectVersion: [] as string[],

      // Edit and New use the same dialog size.
      showDialog_form: false as boolean,
      formMode: undefined as undefined | "edit" | "new",
      dictDetail_edit: undefined as DictScheduleFormDetail | undefined,
      detailCache_edit: undefined as string | undefined,

      showDialog_delete: false as boolean,
      dictDetail_new: undefined as DictNewScheduleFormDetail | undefined,
    };
  },
  actions: {
    async loadProjectNames(): Promise<void> {
      this.arrProjectName = (await invokeMain("getProjectNames")).map((row) => row.name);
    },

    async fetchProjectVersions(name: string): Promise<string[]> {
      return (await invokeMain("getProjectVersions", name)).map((row) => row.version);
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
      this.showDialog_form = false;
      this.showDialog_delete = false;
      this.formMode = undefined;
      this.dictDetail_new = undefined;
      this.dictDetail_edit = undefined;
      this.detailCache_edit = undefined;
    },

    async loadScheduleDetail(name: string): Promise<void> {
      const dictDetail = await invokeMain("getScheduleDetail", name);
      if (dictDetail === undefined) {
        throw new Error(`Schedule not found: ${name}`);
      }

      const settingStore = useSettingStore();
      const { period_start_ms, period_end_ms, ...dictDetailWithoutPeriod } = dictDetail;
      this.dictDetail_edit = {
        ...dictDetailWithoutPeriod,
        period_start: formatTimestampForDateTimeLocal(
          period_start_ms,
          settingStore.timezone,
        ),
        period_end: formatTimestampForDateTimeLocal(period_end_ms, settingStore.timezone),
      };
      this.detailCache_edit = JSON.stringify(this.dictDetail_edit);
    },

    async createSchedule(): Promise<void> {
      if (
        this.dictDetail_new === undefined ||
        this.dictDetail_new.project_id === undefined
      ) {
        return;
      }

      const settingStore = useSettingStore();
      const { intPeriodStartMs, intPeriodEndMs } = getSchedulePeriodTimestamps({
        periodStart: this.dictDetail_new.period_start,
        periodEnd: this.dictDetail_new.period_end,
        timezone: settingStore.timezone,
      });
      const dictTemp: DictScheduleCreate = {
        name: this.dictDetail_new.name,
        project_id: this.dictDetail_new.project_id,
        cron: this.dictDetail_new.cron,
        run_conflict_policy: this.dictDetail_new.run_conflict_policy,
        period_start_ms: intPeriodStartMs,
        period_end_ms: intPeriodEndMs,
        enable: this.dictDetail_new.enable,
        timeout_min: this.dictDetail_new.timeout_min,
        builtin_log_level: this.dictDetail_new.builtin_log_level,
        builtin_record_video: this.dictDetail_new.builtin_record_video,
        builtin_stop_shortcut: this.dictDetail_new.builtin_stop_shortcut,
        builtin_highlight_ui: this.dictDetail_new.builtin_highlight_ui,
        custom_prj_args: this.dictDetail_new.custom_prj_args,
      };
      await invokeMain("createSchedule", dictTemp);
      await this.refreshScheduleList();
    },

    async saveSchedule(): Promise<void> {
      if (
        this.dictDetail_edit === undefined ||
        this.dictDetail_edit.project_id === undefined
      ) {
        return;
      }

      const settingStore = useSettingStore();
      const { intPeriodStartMs, intPeriodEndMs } = getSchedulePeriodTimestamps({
        periodStart: this.dictDetail_edit.period_start,
        periodEnd: this.dictDetail_edit.period_end,
        timezone: settingStore.timezone,
      });
      const dictTemp: DictScheduleUpdate = {
        id: this.dictDetail_edit.id,
        name: this.dictDetail_edit.name,
        project_id: this.dictDetail_edit.project_id,
        cron: this.dictDetail_edit.cron,
        run_conflict_policy: this.dictDetail_edit.run_conflict_policy,
        period_start_ms: intPeriodStartMs,
        period_end_ms: intPeriodEndMs,
        enable: this.dictDetail_edit.enable,
        timeout_min: this.dictDetail_edit.timeout_min,
        builtin_log_level: this.dictDetail_edit.builtin_log_level,
        builtin_record_video: this.dictDetail_edit.builtin_record_video,
        builtin_stop_shortcut: this.dictDetail_edit.builtin_stop_shortcut,
        builtin_highlight_ui: this.dictDetail_edit.builtin_highlight_ui,
        custom_prj_args: this.dictDetail_edit.custom_prj_args,
      };
      await invokeMain("saveSchedule", dictTemp);
      await this.refreshScheduleList();
    },

    async deleteSchedule(): Promise<void> {
      if (this.dictDetail_edit === undefined) {
        return;
      }

      loggerRenderer.info(
        `Delete schedule: ${this.dictDetail_edit.id}-${this.dictDetail_edit.name}`,
      );
      await invokeMain("deleteSchedule", this.dictDetail_edit.id);
      await this.refreshScheduleList();
    },
  },
});
