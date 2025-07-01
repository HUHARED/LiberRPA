<!-- FileName: TaskQueue.vue -->
<template>
  <v-container fluid class="clean-space flex-row-grow-1 fill-height flex-column">
    <v-label class="header-label tab-header">Task Queue</v-label>

    <!-- Table area -->

    <!-- Bug: The "hover" attribute will only work when the window is in the main screen. -->
    <v-data-table
      v-if="queueStore.arrListItem.length !== 0"
      :headers="arrHeader"
      :items="queueStore.arrListItem"
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

      <template #item.estimated_run_time="{ value }">
        <v-chip :text="value" variant="text" size="small" class="clean-space"></v-chip>
      </template>

      <template #item.waiting="{ value }">
        <v-chip
          :border="`${getColor_Waiting(value)} thin opacity-25`"
          :color="getColor_Waiting(value)"
          :text="value"
          variant="text"
          size="x-small"></v-chip>
      </template>

      <template #item.actions="{ item }">
        <div class="d-flex ga-2 justify-start">
          <v-tooltip text="Cancel it." location="bottom">
            <template #activator="{ props }">
              <v-icon
                v-bind="props"
                color="medium-emphasis"
                icon="mdi-stop-circle-outline"
                size="small"
                :disabled="!item.waiting"
                @click="removeWaitingItem(item.name, item.estimated_run_time)">
              </v-icon>
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
  </v-container>
</template>

<script setup lang="ts">
import { onBeforeMount } from "vue";

import { getColor_Source } from "../commonFunc";
import { useQueueStore } from "../store";
import { loggerRenderer } from "@renderer/ipcOfRenderer";

const queueStore = useQueueStore();

onBeforeMount(async () => {
  queueStore.refreshListItem();
});

const arrHeader = [
  { title: "Name", value: "name", align: "start", sortable: false },

  {
    title: "Project",
    align: "center",
    children: [
      { title: "Source", value: "project_source", align: "start", sortable: false },
      { title: "Name", value: "project_name", align: "start", sortable: false },
      {
        title: "Version",
        value: "project_version",
        align: "start",
        sortable: false,
      },
    ],
  },

  {
    title: "Estimated Run Time",
    value: "estimated_run_time",
    align: "center",
    sortable: false,
  },
  { title: "Waiting", value: "waiting", align: "start", sortable: false },
  { title: "Actions", key: "actions", align: "start", sortable: false },
] as any; // use "as any" to make :headers in v-data-table not to complain.

function getColor_Waiting(waiting: boolean): string {
  if (waiting) return "warning";
  else return "grey";
}

function removeWaitingItem(name: string, estimated_run_time): void {
  loggerRenderer.info(`Remove the waiting task: ${name}-${estimated_run_time}`);
  for (let index = 0; index < queueStore.arrWaitingItem.length; index++) {
    const item = queueStore.arrWaitingItem[index];
    if (item.name === name && item.estimated_run_time === estimated_run_time) {
      queueStore.arrWaitingItem.splice(index, 1);
      loggerRenderer.info("Remove completed.");
      queueStore.refreshListItem();
      break;
    }
  }
}
</script>

<style scoped></style>
