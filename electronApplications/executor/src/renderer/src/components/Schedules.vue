<template>
  <v-container fluid class="clean-space flex-row-grow-1 fill-height flex-column">
    <v-label class="header-label tab-header">Schedules</v-label>

    <!-- Header button -->
    <v-container fluid class="pa-1 ma-0 flex-row" style="height: 45px">
      <v-btn
        variant="tonal"
        prepend-icon="mdi-calendar-plus-outline"
        @click="newSchedule()">
        New Schedule
      </v-btn>
    </v-container>

    <HorizontalDivider />

    <!-- Table area -->

    <!-- Bug: The "hover" attribute will only work when the window is in the main screen. -->
    <v-data-table
      v-if="scheduleStore.arrListItem.length !== 0"
      :headers="arrHeader"
      :items="scheduleStore.arrListItem"
      class="clean-space flex-column-grow-1"
      fixed-header
      hide-default-footer
      items-per-page="-1"
      density="compact"
      hover>
      <template #item.project_source="{ value }">
        <v-chip
          :border="`${getProjectSourceColor(value)} thin opacity-25`"
          :color="getProjectSourceColor(value)"
          :text="value"
          variant="text"
          size="x-small"></v-chip>
      </template>

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

    <v-data-table
      v-else
      :headers="arrHeader"
      :items="[]"
      class="clean-space flex-column-grow-1"
      fixed-header
      hide-default-footer
      items-per-page="-1"
      density="compact"
      hover>
    </v-data-table>

    <!-- Dialog: new or edit detail, delete. -->

    <v-dialog v-model="scheduleStore.showDialog_edit_new" width="800px" height="800px">
      <EditScheduleDialog />
      <NewScheduleDialog />
    </v-dialog>

    <v-dialog v-model="scheduleStore.showDialog_delete" width="400px">
      <DeleteScheduleDialog />
    </v-dialog>
  </v-container>
</template>

<script setup lang="ts">
import { onBeforeMount } from "vue";
import type { DataTableHeader } from "vuetify";
import cronstrue from "cronstrue";

import EditScheduleDialog from "./EditScheduleDialog.vue";
import NewScheduleDialog from "./NewScheduleDialog.vue";
import DeleteScheduleDialog from "./DeleteScheduleDialog.vue";
import HorizontalDivider from "./utils/HorizontalDivider.vue";

import { loggerRenderer } from "../Logging/logger";
import { getProjectSourceColor } from "../Common/display";
import { useScheduleStore } from "../Store/scheduleStore";
import { useSettingStore } from "../Store/settingStore";
import { getDefaultSchedulePeriod } from "../Common/time";
import type { DictColumns_Scheduler_ListItem } from "../../../shared/interface";

const scheduleStore = useScheduleStore();
const settingStore = useSettingStore();

onBeforeMount(() => {
  void scheduleStore.loadScheduleList().catch((e: unknown) => {
    loggerRenderer.error(
      `Failed to load Schedules: ${e instanceof Error ? e.message : String(e)}`,
    );
  });
});

function newSchedule(): void {
  loggerRenderer.debug("--newSchedule--");

  const dictDefaultPeriod = getDefaultSchedulePeriod(settingStore.timezone);
  scheduleStore.dictDetail_new = {
    name: "",
    project_source: "local",
    project_id: undefined,
    project_name: undefined,
    project_version: undefined,
    cron: "0 8 * * *",
    when_others_running: "cancel",
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

  scheduleStore.showDialog_edit_new = true;
  scheduleStore.isEditing = "new";
}

const arrHeader: DataTableHeader<DictColumns_Scheduler_ListItem>[] = [
  { title: "Name", value: "name", align: "start", sortable: true },

  {
    title: "Project",
    align: "center",
    children: [
      { title: "Source", value: "project_source", align: "start", sortable: true },
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
  loggerRenderer.info("Edit schedule: " + scheduleName);
  await scheduleStore.loadScheduleDetail(scheduleName);
  scheduleStore.showDialog_edit_new = true;
  scheduleStore.isEditing = "edit";
}

async function openDeleteDialog(scheduleName: string): Promise<void> {
  loggerRenderer.info("Open delete dialog for schedule: " + scheduleName);
  await scheduleStore.loadScheduleDetail(scheduleName);
  scheduleStore.showDialog_delete = true;
}
</script>

<style scoped></style>
