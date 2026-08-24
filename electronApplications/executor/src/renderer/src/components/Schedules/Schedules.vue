<template>
  <v-container fluid class="clean-space flex-row-grow-1 fill-height flex-column">
    <v-label class="header-label tab-header">Schedules</v-label>

    <v-container fluid class="pa-1 ma-0 flex-row" style="height: 45px">
      <v-btn
        variant="tonal"
        prepend-icon="mdi-calendar-plus-outline"
        @click="newSchedule()">
        New Schedule
      </v-btn>
    </v-container>

    <HorizontalDivider />

    <v-data-table
      :headers="arrHeader"
      :items="scheduleStore.arrListItem"
      class="clean-space flex-column-grow-1"
      fixed-header
      hide-default-footer
      items-per-page="-1"
      density="compact"
      hover>
      <template #item.cron="{ value }">
        <v-chip
          :text="
            cronstrue.toString(value, {
              use24HourTimeFormat: true,
              throwExceptionOnParseError: false,
              verbose: true,
            })
          "
          variant="tonal"
          size="small"></v-chip>
      </template>

      <template #item.enable="{ value }">
        <v-chip
          :border="`${getEnabledColor(value)} thin opacity-25`"
          :color="getEnabledColor(value)"
          :text="value ? 'Enabled' : 'Disabled'"
          variant="text"
          size="x-small"></v-chip>
      </template>

      <template #item.actions="{ item }">
        <div class="d-flex ga-2 justify-start">
          <v-tooltip text="Edit Schedule" location="bottom">
            <template #activator="{ props }">
              <v-icon
                v-bind="props"
                color="medium-emphasis"
                icon="mdi-pencil"
                size="small"
                @click="editSchedule(item.name)"></v-icon>
            </template>
          </v-tooltip>

          <v-tooltip text="Delete Schedule" location="bottom">
            <template #activator="{ props }">
              <v-icon
                v-bind="props"
                color="medium-emphasis"
                icon="mdi-delete"
                size="small"
                @click="openDeleteDialog(item.name)"></v-icon>
            </template>
          </v-tooltip>
        </div>
      </template>
    </v-data-table>

    <v-dialog v-model="scheduleStore.showFormDialog" width="800px" height="800px">
      <ScheduleDialog />
    </v-dialog>

    <v-dialog v-model="scheduleStore.showDeleteDialog" width="400px">
      <DeleteScheduleDialog />
    </v-dialog>
  </v-container>
</template>

<script setup lang="ts">
import { onBeforeMount } from "vue";
import type { DataTableHeader } from "vuetify";
import cronstrue from "cronstrue";

import DeleteScheduleDialog from "./DeleteScheduleDialog.vue";
import ScheduleDialog from "./ScheduleDialog.vue";
import HorizontalDivider from "../Common/HorizontalDivider.vue";

import { getDefaultSchedulePeriod } from "../../Common/time";
import { loggerRenderer } from "../../Logging/logger";
import { useScheduleStore } from "../../Store/scheduleStore";
import { useSettingStore } from "../../Store/settingStore";
import type { DictScheduleListItem } from "../../../../shared/schedule";

const scheduleStore = useScheduleStore();
const settingStore = useSettingStore();

onBeforeMount(() => {
  void Promise.all([
    scheduleStore.loadScheduleList(),
    scheduleStore.loadProjectNames(),
  ]).catch((e: unknown) => {
    loggerRenderer.error(
      `Failed to initialize Schedules: ${e instanceof Error ? e.message : String(e)}`,
    );
  });
});

function newSchedule(): void {
  loggerRenderer.debug("--newSchedule--");

  scheduleStore.resetProjectVersions();
  const dictDefaultPeriod = getDefaultSchedulePeriod(settingStore.timezone);
  scheduleStore.dictDetailNew = {
    name: "",
    project_id: undefined,
    project_name: undefined,
    project_version: undefined,
    cron: "0 8 * * *",
    run_conflict_policy: "skip",
    period_start: dictDefaultPeriod.strPeriodStartLocal,
    period_end: dictDefaultPeriod.strPeriodEndLocal,
    enable: true,
    timeout_min: 0,
    builtin_log_level: "DEBUG",
    builtin_record_video: true,
    builtin_stop_shortcut: true,
    builtin_highlight_ui: false,
    custom_prj_args: [],
  };

  scheduleStore.formMode = "new";
  scheduleStore.showFormDialog = true;
}

const arrHeader: DataTableHeader<DictScheduleListItem>[] = [
  { title: "Name", value: "name", align: "start", sortable: true },
  {
    title: "Project",
    align: "center",
    children: [
      { title: "Name", value: "project_name", align: "start", sortable: true },
      {
        title: "Version",
        value: "project_version",
        align: "start",
        sortable: true,
      },
    ],
  },
  { title: "Schedule", value: "cron", align: "start", sortable: true },
  { title: "Enabled", value: "enable", align: "start", sortable: true },
  { title: "Actions", key: "actions", align: "start", sortable: false },
];

function getEnabledColor(enable: boolean): string {
  return enable ? "success" : "grey";
}

async function editSchedule(scheduleName: string): Promise<void> {
  loggerRenderer.info(`Edit schedule: ${scheduleName}`);
  await scheduleStore.loadScheduleDetail(scheduleName);

  const detail = scheduleStore.dictDetailEdit;
  if (detail === undefined) {
    return;
  }

  await scheduleStore.loadProjectNames();
  scheduleStore.setProjectVersions(
    await scheduleStore.fetchProjectVersions(detail.project_name),
  );
  scheduleStore.formMode = "edit";
  scheduleStore.showFormDialog = true;
}

async function openDeleteDialog(scheduleName: string): Promise<void> {
  loggerRenderer.info(`Open delete dialog for schedule: ${scheduleName}`);
  await scheduleStore.loadScheduleDetail(scheduleName);
  scheduleStore.showDeleteDialog = true;
}
</script>

<style scoped></style>
