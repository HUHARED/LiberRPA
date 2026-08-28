<!-- FileName: RunQueue.vue -->
<template>
  <v-container fluid class="clean-space flex-row-grow-1 fill-height flex-column">
    <v-label class="header-label tab-header">Run Queue</v-label>

    <!-- Bug: The hover attribute only works when the window is on the primary screen. -->
    <v-data-table
      :headers="arrHeader"
      :items="runQueueStore.arrListItem"
      item-value="queue_id"
      class="clean-space flex-column-grow-1"
      fixed-header
      hide-default-footer
      items-per-page="-1"
      density="compact"
      hover>
      <template #item.estimated_run_at_ms="{ value }">
        <v-chip
          :text="formatTimestamp(value, settingStore.timezone)"
          variant="text"
          size="small"
          class="clean-space"></v-chip>
      </template>

      <template #item.waiting="{ value }">
        <v-chip
          :border="`${getWaitingColor(value)} thin opacity-25`"
          :color="getWaitingColor(value)"
          :text="value ? 'Waiting' : 'Pending'"
          variant="text"
          size="x-small"></v-chip>
      </template>

      <template #item.actions="{ item }">
        <div class="d-flex ga-2 justify-start">
          <v-tooltip text="Cancel Waiting Run" location="bottom">
            <template #activator="{ props }">
              <v-icon
                v-bind="props"
                color="medium-emphasis"
                icon="mdi-stop-circle-outline"
                size="small"
                :disabled="!item.waiting"
                @click="removeWaitingItem(item)">
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

import { loggerRenderer } from "../../Logging/logger";
import { useRunQueueStore } from "../../Store/runQueueStore";
import { useSettingStore } from "../../Store/settingStore";
import { formatTimestamp } from "../../Common/time";
import { getErrorMessage } from "../../../../shared/error";
import type { Dict_ListItem_RunQueue } from "../../../../shared/run";

const runQueueStore = useRunQueueStore();
const settingStore = useSettingStore();

onBeforeMount(() => {
  void runQueueStore.refreshRunQueue().catch((e: unknown) => {
    loggerRenderer.error(`Failed to load Run Queue: ${getErrorMessage(e)}`);
  });
});

const arrHeader: DataTableHeader<Dict_ListItem_RunQueue>[] = [
  { title: "Schedule", value: "schedule_name", align: "start", sortable: false },
  {
    title: "Project",
    align: "center",
    children: [
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
    title: "Scheduled Time",
    value: "estimated_run_at_ms",
    align: "center",
    sortable: false,
  },
  { title: "State", value: "waiting", align: "start", sortable: false },
  { title: "Actions", key: "actions", align: "start", sortable: false },
];

function getWaitingColor(waiting: boolean): string {
  return waiting ? "warning" : "inactive";
}

async function removeWaitingItem(item: Dict_ListItem_RunQueue): Promise<void> {
  loggerRenderer.info(
    `Cancel waiting Run: ${item.schedule_name}-${item.estimated_run_at_ms}`,
  );
  await runQueueStore.cancelWaitingRun(item.queue_id);
}
</script>

<style scoped></style>
