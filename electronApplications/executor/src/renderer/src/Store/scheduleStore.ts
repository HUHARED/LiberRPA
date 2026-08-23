import { defineStore } from "pinia";

import { invokeMain } from "../IPC/ipc";
import { loggerRenderer } from "../Logging/logger";
import {
  formatTimestampForDateTimeLocal,
  parseDateTimeLocalToTimestamp,
} from "../Common/time";
import { useSettingStore } from "./settingStore";
import type {
  DictColumns_Scheduler_ListItem,
  DictColumns_Scheduler_Detail,
  DictColumns_Scheduler_Detail_ToUpdate,
  DictColumns_Scheduler_Detail_BeforeInsert,
  DictColumns_Scheduler_Detail_ToInsert,
} from "../../../shared/interface";

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
  actions: {
    async loadScheduleList(): Promise<void> {
      if (this.arrListItem.length === 0) {
        const arrRow = await invokeMain("selectSchedulerList");

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
    },

    async refreshScheduleList(): Promise<void> {
      this.arrListItem = [];
      await this.loadScheduleList();
      this.showDialog_edit_new = false;
      this.showDialog_delete = false;
    },

    async loadScheduleDetail(name: string): Promise<void> {
      const dictRow = await invokeMain("selectSchedulerDetail", name);
      if (dictRow === undefined) {
        throw new Error(`Schedule not found: ${name}`);
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
      await invokeMain("insertSchedulerDetail", dictTemp);
      await this.refreshScheduleList();
    },

    async saveSchedule(): Promise<void> {
      if (this.dictDetail_edit === undefined) {
        return;
      }

      const settingStore = useSettingStore();
      const { intPeriodStartMs, intPeriodEndMs } = getSchedulePeriodTimestamps({
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
      await invokeMain("updateSchedulerDetail", dictTemp);
      await this.refreshScheduleList();
    },

    async deleteSchedule(): Promise<void> {
      if (this.dictDetail_edit === undefined) {
        return;
      }

      loggerRenderer.info(
        `Delete schedule: ${this.dictDetail_edit.id}-${this.dictDetail_edit.name}`,
      );
      await invokeMain("deleteScheduler", this.dictDetail_edit.id);
      await this.refreshScheduleList();
    },
  },
});
