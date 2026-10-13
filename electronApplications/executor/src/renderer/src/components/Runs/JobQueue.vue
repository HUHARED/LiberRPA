<!-- FileName: JobQueue.vue -->
<template>
  <v-container fluid class="clean-space flex-row-grow-1 fill-height flex-column">
    <v-label class="header-label tab-header">Job Queue</v-label>

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

      <template #item.due_at_ms="{ value }">
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
              :icon="
                item.state === JobQueueState.Running
                  ? 'mdi-stop-circle-outline'
                  : 'mdi-cancel'
              "
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
      <template #item.due_at_ms="{ value }">
        {{ formatTimestamp(value, settingStore.timezone) }}
      </template>
    </v-data-table>
  </v-container>
</template>

<script setup lang="ts">
import { computed, onBeforeMount, ref } from "vue";
import type { DataTableHeader } from "vuetify";

import { loggerRenderer } from "../../Logging/logger";
import { useJobQueueStore } from "../../Store/jobQueueStore";
import { useSettingStore } from "../../Store/settingStore";
import { formatTimestamp } from "../../Common/time";
import { getErrorMessage } from "../../../../shared/error";
import { RunSource, JobQueueState, type JobQueueItem } from "../../../../shared/run";

const jobQueueStore = useJobQueueStore();
const settingStore = useSettingStore();
const setPendingAction = ref(new Set<string>());

const arrCurrentRun = computed(() =>
  jobQueueStore.arrListItem.filter((item) => item.state !== JobQueueState.Pending),
);
const arrUpcomingTrigger = computed(() =>
  jobQueueStore.arrListItem.filter((item) => item.state === JobQueueState.Pending),
);

const dictSourceLabel: Record<RunSource, string> = {
  [RunSource.Local]: "Local",
  [RunSource.Console]: "Console",
};
const dictQueueState: Record<JobQueueState, { label: string; color: string }> = {
  [JobQueueState.Pending]: { label: "Pending", color: "inactive" },
  [JobQueueState.WaitingRetry]: { label: "Waiting for Retry", color: "info" },
  [JobQueueState.Waiting]: { label: "Waiting", color: "warning" },
  [JobQueueState.Starting]: { label: "Starting", color: "info" },
  [JobQueueState.Running]: { label: "Running", color: "success" },
  [JobQueueState.Stopping]: { label: "Stopping", color: "warning" },
};

const arrProjectHeader: DataTableHeader<JobQueueItem>[] = [
  { title: "Name", value: "project_name", align: "start", sortable: false },
  { title: "Version", value: "project_version", align: "start", sortable: false },
];
const arrCurrentHeader: DataTableHeader<JobQueueItem>[] = [
  { title: "Source", value: "source", align: "start", sortable: false },
  { title: "Schedule", value: "schedule_name", align: "start", sortable: false },
  { title: "Project", align: "center", children: arrProjectHeader },
  {
    title: "Due At",
    value: "due_at_ms",
    align: "center",
    sortable: false,
  },
  { title: "Started At", value: "started_at_ms", align: "center", sortable: false },
  { title: "Status", value: "state", align: "start", sortable: false },
  { title: "Actions", key: "actions", align: "start", sortable: false },
];
const arrUpcomingHeader: DataTableHeader<JobQueueItem>[] = [
  { title: "Schedule", value: "schedule_name", align: "start", sortable: false },
  { title: "Project", align: "center", children: arrProjectHeader },
  {
    title: "Due At",
    value: "due_at_ms",
    align: "center",
    sortable: false,
  },
];

function getControlLabel(item: JobQueueItem): string {
  if (item.state === JobQueueState.WaitingRetry) return "Cancel Retries";
  if (item.state === JobQueueState.Waiting) return "Cancel";
  if (item.state === JobQueueState.Running && item.history_id !== null) {
    return "Stop";
  }
  return "";
}

async function controlRun(item: JobQueueItem): Promise<void> {
  if (setPendingAction.value.has(item.queue_id) || !getControlLabel(item)) return;
  setPendingAction.value.add(item.queue_id);
  try {
    if (item.state === JobQueueState.Running && item.history_id !== null) {
      await jobQueueStore.stopCurrentRun(item.history_id);
    } else {
      await jobQueueStore.cancelQueuedRun(item.queue_id);
    }
  } catch (e: unknown) {
    loggerRenderer.error(`Failed to control Run: ${getErrorMessage(e)}`);
  } finally {
    setPendingAction.value.delete(item.queue_id);
  }
}

onBeforeMount(() => {
  void jobQueueStore.refreshJobQueue().catch((e: unknown) => {
    loggerRenderer.error(`Failed to load Job Queue: ${getErrorMessage(e)}`);
  });
});
</script>

<style scoped></style>
