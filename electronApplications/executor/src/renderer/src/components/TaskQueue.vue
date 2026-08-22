<!-- FileName: TaskQueue.vue -->
<template>
  <v-container fluid class="clean-space flex-row-grow-1 fill-height flex-column">
    <v-label class="header-label tab-header">Task Queue</v-label>

    <!-- Bug: The hover attribute only works when the window is on the primary screen. -->
    <v-data-table
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

      <template #item.estimated_run_at_ms="{ value }">
        <v-chip
          :text="formatTimestamp(value, settingStore.timezone)"
          variant="text"
          size="small"
          class="clean-space"></v-chip>
      </template>

      <template #item.waiting="{ value }">
        <v-chip
          :border="`${getColorWaiting(value)} thin opacity-25`"
          :color="getColorWaiting(value)"
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
                @click="removeWaitingItem(item.name, item.estimated_run_at_ms)">
              </v-icon>
            </template>
          </v-tooltip>
        </div>
      </template>
    </v-data-table>
  </v-container>
</template>

<script setup lang="ts">
import { onBeforeMount } from "vue";
import type { DataTableHeader } from "vuetify";

import { getColor_Source } from "../commonFunc";
import { loggerRenderer } from "../ipcOfRenderer";
import { useQueueStore, useSettingStore } from "../store";
import { formatTimestamp } from "../time";
import type { Dict_TaskQueue_ListItem } from "../../../shared/interface";

const queueStore = useQueueStore();
const settingStore = useSettingStore();

onBeforeMount(() => {
  queueStore.refreshListItem();
});

const arrHeader: DataTableHeader<Dict_TaskQueue_ListItem>[] = [
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
    value: "estimated_run_at_ms",
    align: "center",
    sortable: false,
  },
  { title: "Waiting", value: "waiting", align: "start", sortable: false },
  { title: "Actions", key: "actions", align: "start", sortable: false },
];

function getColorWaiting(waiting: boolean): string {
  return waiting ? "warning" : "grey";
}

function removeWaitingItem(name: string, intEstimatedRunAtMs: number): void {
  loggerRenderer.info(`Remove waiting task: ${name}-${intEstimatedRunAtMs}`);
  const intItemIndex = queueStore.arrWaitingItem.findIndex(
    (dictItem) =>
      dictItem.name === name && dictItem.estimated_run_at_ms === intEstimatedRunAtMs,
  );
  if (intItemIndex === -1) {
    return;
  }

  queueStore.arrWaitingItem.splice(intItemIndex, 1);
  queueStore.refreshListItem();
}
</script>

<style scoped></style>
