<!-- FileName: RunQueue.vue -->
<template>
  <v-container fluid class="clean-space flex-row-grow-1 fill-height flex-column">
    <v-label class="header-label tab-header">Run Queue</v-label>

    <!-- Bug: The hover attribute only works when the window is on the primary screen. -->
    <v-label class="align-self-start text-subtitle-2 my-2">Current Jobs</v-label>
    <v-data-table
      :headers="arrCurrentHeader"
      :items="arrCurrentRun"
      item-value="queue_id"
      class="clean-space flex-column-grow-1 w-100"
      fixed-header
      height="100%"
      hide-default-footer
      :items-per-page="-1"
      no-data-text="No current jobs."
      density="compact"
      hover>
      <template #item.source="{ item }">
        {{ dictSourceLabel[item.source] }}
      </template>

      <template #item.schedule_name="{ value }">
        {{ value ?? "—" }}
      </template>

      <template #item.estimated_run_at_ms="{ value }">
        {{ value === null ? "—" : formatTimestamp(value, settingStore.timezone) }}
      </template>

      <template #item.started_at_ms="{ value }">
        {{ value === null ? "—" : formatTimestamp(value, settingStore.timezone) }}
      </template>

      <template #item.state="{ item }">
        <v-chip
          :border="`${dictQueueState[item.state].color} thin opacity-25`"
          :color="dictQueueState[item.state].color"
          :text="dictQueueState[item.state].label"
          variant="text"
          size="x-small"></v-chip>
      </template>

      <template #item.actions="{ item }">
        <v-tooltip
          v-if="getControlLabel(item)"
          :text="getControlLabel(item)"
          location="bottom"
          :open-on-focus="false">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              :aria-label="getControlLabel(item)"
              :loading="setPendingAction.has(item.queue_id)"
              :disabled="setPendingAction.has(item.queue_id)"
              color="medium-emphasis"
              icon="mdi-stop-circle-outline"
              variant="text"
              size="x-small"
              @click="controlRun(item)"></v-btn>
          </template>
        </v-tooltip>
      </template>
    </v-data-table>

    <v-label class="align-self-start text-subtitle-2 my-2">Upcoming Triggers</v-label>
    <v-data-table
      :headers="arrUpcomingHeader"
      :items="arrUpcomingTrigger"
      item-value="queue_id"
      class="clean-space flex-column-grow-1 w-100"
      fixed-header
      height="100%"
      hide-default-footer
      :items-per-page="-1"
      no-data-text="No upcoming triggers."
      density="compact"
      hover>
      <template #item.estimated_run_at_ms="{ value }">
        {{ formatTimestamp(value, settingStore.timezone) }}
      </template>
    </v-data-table>
  </v-container>
</template>

<script setup lang="ts">
import { computed, onBeforeMount, ref } from "vue";
import type { DataTableHeader } from "vuetify";

import { loggerRenderer } from "../../Logging/logger";
import { useRunQueueStore } from "../../Store/runQueueStore";
import { useSettingStore } from "../../Store/settingStore";
import { formatTimestamp } from "../../Common/time";
import { getErrorMessage } from "../../../../shared/error";
import { RunSource, RunQueueState, type RunQueueItem } from "../../../../shared/run";

const runQueueStore = useRunQueueStore();
const settingStore = useSettingStore();
const setPendingAction = ref(new Set<string>());

const arrCurrentRun = computed(() =>
  runQueueStore.arrListItem.filter((item) => item.state !== RunQueueState.Pending),
);
const arrUpcomingTrigger = computed(() =>
  runQueueStore.arrListItem.filter((item) => item.state === RunQueueState.Pending),
);

const dictSourceLabel: Record<RunSource, string> = {
  [RunSource.Local]: "Local",
  [RunSource.Console]: "Console",
};
const dictQueueState: Record<RunQueueState, { label: string; color: string }> = {
  [RunQueueState.Pending]: { label: "Pending", color: "inactive" },
  [RunQueueState.WaitingRetry]: { label: "Waiting for Retry", color: "info" },
  [RunQueueState.Waiting]: { label: "Waiting", color: "warning" },
  [RunQueueState.Starting]: { label: "Starting", color: "info" },
  [RunQueueState.Running]: { label: "Running", color: "success" },
  [RunQueueState.Stopping]: { label: "Stopping", color: "warning" },
};

const arrProjectHeader: DataTableHeader<RunQueueItem>[] = [
  { title: "Name", value: "project_name", align: "start", sortable: false },
  { title: "Version", value: "project_version", align: "start", sortable: false },
];
const arrCurrentHeader: DataTableHeader<RunQueueItem>[] = [
  { title: "Source", value: "source", align: "start", sortable: false },
  { title: "Schedule", value: "schedule_name", align: "start", sortable: false },
  { title: "Project", align: "center", children: arrProjectHeader },
  {
    title: "Scheduled At",
    value: "estimated_run_at_ms",
    align: "center",
    sortable: false,
  },
  { title: "Started At", value: "started_at_ms", align: "center", sortable: false },
  { title: "Status", value: "state", align: "start", sortable: false },
  { title: "Actions", key: "actions", align: "start", sortable: false },
];
const arrUpcomingHeader: DataTableHeader<RunQueueItem>[] = [
  { title: "Schedule", value: "schedule_name", align: "start", sortable: false },
  { title: "Project", align: "center", children: arrProjectHeader },
  {
    title: "Scheduled At",
    value: "estimated_run_at_ms",
    align: "center",
    sortable: false,
  },
];

function getControlLabel(item: RunQueueItem): string {
  if (item.state === RunQueueState.WaitingRetry) return "Cancel Retry";
  if (item.state === RunQueueState.Waiting) return "Cancel Run";
  if (item.state === RunQueueState.Running && item.history_id !== null) {
    return "Stop Current Run";
  }
  return "";
}

async function controlRun(item: RunQueueItem): Promise<void> {
  if (setPendingAction.value.has(item.queue_id) || !getControlLabel(item)) return;
  setPendingAction.value.add(item.queue_id);
  try {
    if (item.state === RunQueueState.Running && item.history_id !== null) {
      await runQueueStore.stopCurrentRun(item.history_id);
    } else {
      await runQueueStore.cancelQueuedRun(item.queue_id);
    }
  } catch (e: unknown) {
    loggerRenderer.error(`Failed to control Run: ${getErrorMessage(e)}`);
  } finally {
    setPendingAction.value.delete(item.queue_id);
  }
}

onBeforeMount(() => {
  void runQueueStore.refreshRunQueue().catch((e: unknown) => {
    loggerRenderer.error(`Failed to load Run Queue: ${getErrorMessage(e)}`);
  });
});
</script>

<style scoped></style>
