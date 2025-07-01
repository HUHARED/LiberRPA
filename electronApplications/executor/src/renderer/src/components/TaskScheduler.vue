<!-- FileName: TaskScheduler.vue -->
<template>
  <v-container fluid class="clean-space flex-row-grow-1 fill-height flex-column">
    <v-label class="header-label tab-header">Task Scheduler</v-label>

    <!-- Header button -->
    <v-container fluid class="pa-1 ma-0 flex-row" style="height: 45px">
      <v-btn
        variant="tonal"
        prepend-icon="mdi-calendar-plus-outline"
        @click="newTaskScheduler()">
        New
      </v-btn>
    </v-container>

    <HorizontalDivider />

    <!-- Table area -->

    <!-- Bug: The "hover" attribute will only work when the window is in the main screen. -->
    <v-data-table
      v-if="schedulerStore.arrListItem.length !== 0"
      :headers="arrHeader"
      :items="schedulerStore.arrListItem"
      class="clean-space flex-column-grow-1"
      fixed-header
      hide-default-footer
      items-per-page="-1"
      density="compact"
      hover>
      <template #item.project_source="{ value }">
        <v-chip
          :border="`${getColor_Source(value)} thin opacity-25`"
          :color="getColor_Source(value)"
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
          :border="`${getColor_Enable(value)} thin opacity-25`"
          :color="getColor_Enable(value)"
          :text="value"
          variant="text"
          size="x-small"></v-chip>
      </template>

      <template #item.actions="{ item }">
        <div class="d-flex ga-2 justify-start">
          <v-icon
            color="medium-emphasis"
            icon="mdi-pencil"
            size="small"
            @click="editScheduler(item.name)"></v-icon>

          <v-icon
            color="medium-emphasis"
            icon="mdi-delete"
            size="small"
            @click="openDeleteDialog(item.name)"></v-icon>
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

    <v-dialog v-model="schedulerStore.showDialog_edit_new" width="800px" height="800px">
      <TaskScheduler_Dialog_Edit />
      <TaskScheduler_Dialog_New />
    </v-dialog>

    <v-dialog v-model="schedulerStore.showDialog_delete" width="400px">
      <TaskScheduler_Dialog_Delete />
    </v-dialog>
  </v-container>
</template>

<script setup lang="ts">
import { onBeforeMount } from "vue";
import cronstrue from "cronstrue";
import moment from "moment";

import TaskScheduler_Dialog_Edit from "./TaskScheduler_Dialog_Edit.vue";
import TaskScheduler_Dialog_New from "./TaskScheduler_Dialog_New.vue";
import TaskScheduler_Dialog_Delete from "./TaskScheduler_Dialog_Delete.vue";
import HorizontalDivider from "./utils/HorizontalDivider.vue";

import { loggerRenderer } from "../ipcOfRenderer";
import { getColor_Source } from "../commonFunc";
import { useSchedulerStore } from "../store";

const schedulerStore = useSchedulerStore();

onBeforeMount(async () => {
  await schedulerStore.dbSelectSchedulerList();
});

function newTaskScheduler(): void {
  loggerRenderer.debug("--newTaskScheduler--");

  // Generate basic data.
  schedulerStore.dictDetail_new = {
    name: "",
    project_source: "local",
    project_id: undefined,
    project_name: undefined,
    project_version: undefined,
    cron: "0 8 * * *",
    when_others_running: "cancel",
    period_start: moment(new Date()).format("YYYY-MM-DD [00:00:00]"),
    period_end: "2084-04-04 00:00:00",
    enable: true,
    timeout_min: 0,
    buildin_log_level: "DEBUG",
    buildin_record_video: true,
    buildin_stop_shortcut: true,
    buildin_highlight_ui: false,
    custom_prj_args: [],
  };

  schedulerStore.showDialog_edit_new = true;
  schedulerStore.isEditing = "new";
}

const arrHeader = [
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

  { title: "Cron", value: "cron", align: "start", sortable: true },
  { title: "Enable", value: "enable", align: "start", sortable: true },
  { title: "Actions", key: "actions", align: "start", sortable: false },
] as any; // use "as any" to make :headers in v-data-table not to complain.

function getColor_Enable(enable: boolean): string {
  if (enable) return "success";
  else return "grey";
}

async function editScheduler(schedulerName: string): Promise<void> {
  loggerRenderer.info("Edit scheduler: " + schedulerName);
  await schedulerStore.dbSelectSchedulerDetail(schedulerName);
  schedulerStore.showDialog_edit_new = true;
  schedulerStore.isEditing = "edit";
}

async function openDeleteDialog(schedulerName: string): Promise<void> {
  loggerRenderer.info("Open delete dialog for scheduler: " + schedulerName);
  await schedulerStore.dbSelectSchedulerDetail(schedulerName);
  schedulerStore.showDialog_delete = true;
}
</script>

<style scoped></style>
