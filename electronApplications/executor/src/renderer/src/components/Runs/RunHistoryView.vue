<!-- FileName: RunHistoryView.vue -->
<template>
  <v-container fluid class="clean-space flex-row-grow-1 fill-height flex-column">
    <v-label class="header-label tab-header">Run History</v-label>

    <!-- Bug: The hover attribute only works when the window is on the primary screen. -->
    <v-data-table-server
      :headers="arrHeader"
      :items="runHistoryStore.arrListItem"
      :items-length="runHistoryStore.itemLength"
      :items-per-page="itemPerPage"
      :items-per-page-options="arrItemsPerPageOptions"
      :search="search"
      class="clean-space flex-column-grow-1"
      fixed-header
      density="compact"
      hover
      multi-sort
      @update:options="handleTableOptionsUpdate($event)">
      <template #item.project_name="{ value }">
        <span :title="value" class="d-block text-truncate">{{ value }}</span>
      </template>

      <template #item.schedule_name="{ value }">
        {{ value ?? "—" }}
      </template>

      <template #item.source="{ item }">
        <v-chip
          :border="`${DICT_RUN_SOURCE_COLOR[item.source]} thin opacity-25`"
          :color="DICT_RUN_SOURCE_COLOR[item.source]"
          :text="DICT_RUN_SOURCE_LABEL[item.source]"
          variant="text"
          size="x-small"></v-chip>
      </template>

      <template #item.run_started_at_ms="{ value }">
        <v-chip
          :text="formatTimestamp(value, settingStore.timezone)"
          variant="text"
          size="small"
          class="clean-space"></v-chip>
      </template>

      <template #item.run_ended_at_ms="{ item }">
        <v-chip
          :text="
            item.run_ended_at_ms === null && item.status === RunStatus.Running
              ? '—'
              : formatTimestamp(item.run_ended_at_ms, settingStore.timezone)
          "
          variant="text"
          size="small"
          class="clean-space"></v-chip>
      </template>

      <template #item.duration="{ item }">
        {{ formatDuration(item.run_started_at_ms, item.run_ended_at_ms) }}
      </template>

      <template #item.status="{ value }">
        <v-chip
          :border="`${getStatusColor(value)} thin opacity-25`"
          :color="getStatusColor(value)"
          :text="getStatusLabel(value)"
          variant="text"
          size="x-small"></v-chip>
      </template>

      <template #item.actions="{ item }">
        <div class="d-flex align-center ga-2 justify-start">
          <v-tooltip text="View Run Details" location="bottom" :open-on-focus="false">
            <template #activator="{ props }">
              <v-icon
                v-bind="props"
                icon="mdi-eye-outline"
                size="small"
                aria-label="View Run Details"
                @click="showRunDetails(item.id)" />
            </template>
          </v-tooltip>

          <v-tooltip text="Open Log Folder" location="bottom" :open-on-focus="false">
            <template #activator="{ props }">
              <v-icon
                v-bind="props"
                color="medium-emphasis"
                icon="mdi-file-document-outline"
                size="small"
                @click="openLogFolder(item.id)"></v-icon>
            </template>
          </v-tooltip>

          <span
            v-if="item.status === RunStatus.Running && setStoppingRunId.has(item.id)"
            class="text-body-2">
            Stop requested
          </span>

          <v-tooltip
            v-else-if="item.status === RunStatus.Running"
            text="Stop Run"
            location="bottom"
            :open-on-focus="false">
            <template #activator="{ props }">
              <v-icon
                v-bind="props"
                color="medium-emphasis"
                icon="mdi-stop-circle-outline"
                size="small"
                aria-label="Stop Run"
                :disabled="setPendingStop.has(item.id)"
                @click="stopRun(item.id)"></v-icon>
            </template>
          </v-tooltip>

          <v-tooltip
            v-else-if="
              item.source === RunSource.Local &&
              item.run_ended_at_ms !== null &&
              item.status !== RunStatus.Unknown
            "
            text="Run Most Recently Installed Version"
            location="bottom"
            :open-on-focus="false">
            <template #activator="{ props }">
              <v-icon
                v-bind="props"
                color="medium-emphasis"
                icon="mdi-replay"
                size="small"
                :disabled="setPendingRerun.has(item.id)"
                @click="openRerunDialog(item.id)"></v-icon>
            </template>
          </v-tooltip>
        </div>
      </template>

      <template #body.prepend="{ columns }">
        <tr>
          <td v-for="column in columns" :key="String(column.key)">
            <v-text-field
              v-if="column.key === 'schedule_name'"
              v-model="runHistoryStore.filterScheduleName"
              aria-label="Filter by Schedule"
              class="pa-0 ma-0 pl-2 pr-2"
              density="compact"
              hide-details
              variant="underlined"></v-text-field>

            <v-text-field
              v-else-if="column.key === 'project_name'"
              v-model="runHistoryStore.filterProjectName"
              aria-label="Filter by Project Name"
              class="pa-0 ma-0 pl-2 pr-2"
              density="compact"
              hide-details
              variant="underlined"></v-text-field>

            <v-text-field
              v-else-if="column.key === 'project_version'"
              v-model="runHistoryStore.filterProjectVersion"
              aria-label="Filter by Project Version"
              class="pa-0 ma-0 pl-2 pr-2"
              density="compact"
              hide-details
              variant="underlined"></v-text-field>

            <v-select
              v-else-if="column.key === 'status'"
              v-model="runHistoryStore.filterStatus"
              aria-label="Filter by Status"
              variant="underlined"
              class="pa-0 ma-0 pl-2 pr-2"
              density="compact"
              hide-details
              clearable
              :items="ARR_RUN_STATUS_OPTION"></v-select>

            <v-select
              v-else-if="column.key === 'source'"
              v-model="runHistoryStore.filterSource"
              aria-label="Filter by Source"
              variant="underlined"
              class="pa-0 ma-0 pl-2 pr-2"
              density="compact"
              hide-details
              clearable
              :items="ARR_RUN_SOURCE_OPTION"></v-select>
          </td>
        </tr>
      </template>
    </v-data-table-server>

    <PackageRunDialog
      v-if="rerunPackage"
      :package-details="rerunPackage"
      @close="rerunPackage = undefined" />

    <RunDetailsDialog
      v-if="runHistoryStore.runDetails"
      :details="runHistoryStore.runDetails"
      :source-label="DICT_RUN_SOURCE_LABEL[runHistoryStore.runDetails.source]"
      @close="runHistoryStore.closeRunDetails()" />
  </v-container>
</template>

<script setup lang="ts">
import { computed, onBeforeMount, onBeforeUnmount, ref, watch, type Ref } from "vue";
import { debounce } from "lodash";
import type { DataTableHeader } from "vuetify";

import PackageRunDialog from "../Packages/PackageRunDialog.vue";
import RunDetailsDialog from "./RunDetailsDialog.vue";

import type { PackageDetails } from "../../../../shared/package";

import { getErrorMessage } from "../../../../shared/error";
import {
  RunSource,
  RunStatus,
  type RunHistoryItem,
  type RunHistoryFilters,
  type RunHistoryQueryOptions,
  JobQueueState,
} from "../../../../shared/run";

import { invokeMain } from "../../IPC/ipc";
import { loggerRenderer } from "../../Logging/logger";
import { cloneJsonSerializable } from "../../Common/json";
import { useRunHistoryStore } from "../../Store/runHistoryStore";
import { useJobQueueStore } from "../../Store/jobQueueStore";
import { useSettingStore } from "../../Store/settingStore";
import { formatTimestamp } from "../../Common/time";

const DICT_RUN_SOURCE_LABEL: Record<RunSource, string> = {
  [RunSource.Local]: "Local",
  [RunSource.Console]: "Console",
};

const DICT_RUN_SOURCE_COLOR: Record<RunSource, string> = {
  [RunSource.Local]: "info",
  [RunSource.Console]: "success",
};

const ARR_RUN_SOURCE_OPTION = Object.values(RunSource).map((source) => ({
  title: DICT_RUN_SOURCE_LABEL[source],
  value: source,
}));

const DICT_RUN_STATUS_DISPLAY: Record<RunStatus, { title: string; color: string }> = {
  [RunStatus.Running]: { title: "Running", color: "success" },
  [RunStatus.Completed]: { title: "Completed", color: "inactive" },
  [RunStatus.Error]: { title: "Error", color: "error" },
  [RunStatus.Canceled]: { title: "Canceled", color: "warning" },
  [RunStatus.TimedOut]: { title: "Timed Out", color: "run-timeout" },
  [RunStatus.Interrupted]: { title: "Interrupted", color: "run-interrupted" },
  [RunStatus.Unknown]: { title: "Unknown", color: "inactive" },
};

const ARR_RUN_STATUS_OPTION = Object.values(RunStatus).map((status) => ({
  title: DICT_RUN_STATUS_DISPLAY[status].title,
  value: status,
}));

const runHistoryStore = useRunHistoryStore();
const jobQueueStore = useJobQueueStore();
const settingStore = useSettingStore();

const setPendingStop = ref(new Set<number>());
const setPendingRerun = ref(new Set<number>());
const rerunPackage = ref<PackageDetails>();

const setStoppingRunId = computed(() => {
  const setRunId = new Set<number>();
  for (const item of jobQueueStore.arrListItem) {
    if (item.state === JobQueueState.Stopping && item.history_id !== null) {
      setRunId.add(item.history_id);
    }
  }
  return setRunId;
});

async function showRunDetails(id: number): Promise<void> {
  try {
    await runHistoryStore.loadRunDetails(id);
  } catch (e: unknown) {
    loggerRenderer.error(`Failed to load Run Details: ${getErrorMessage(e)}`);
  }
}

const itemPerPage: Ref<15 | 50 | 100> = ref(15);

const arrItemsPerPageOptions = [
  { value: 15, title: "15" },
  { value: 50, title: "50" },
  { value: 100, title: "100" },
];

const dictSearch = computed<RunHistoryFilters>(() => {
  return {
    schedule_name: runHistoryStore.filterScheduleName,
    project_name: runHistoryStore.filterProjectName,
    project_version: runHistoryStore.filterProjectVersion,
    status: runHistoryStore.filterStatus,
    source: runHistoryStore.filterSource,
  };
});

const search = ref(JSON.stringify(dictSearch.value));

const debouncedUpdateSearch = debounce(() => {
  search.value = JSON.stringify(dictSearch.value);
}, 300);

watch(
  dictSearch,
  () => {
    debouncedUpdateSearch();
  },
  { deep: true },
);

type RunHistoryTableOptions = Omit<RunHistoryQueryOptions, "search"> & {
  search: string;
};

async function handleTableOptionsUpdate(
  optionsDict: RunHistoryTableOptions,
): Promise<void> {
  await runHistoryStore.loadRunHistoryPage({
    page: optionsDict.page,
    itemsPerPage: optionsDict.itemsPerPage,
    sortBy: cloneJsonSerializable(optionsDict.sortBy),
    search: cloneJsonSerializable(dictSearch.value),
  });
}

const arrHeader: DataTableHeader<RunHistoryItem>[] = [
  { title: "Schedule", value: "schedule_name", align: "start", sortable: true },
  {
    title: "Project",
    align: "center",
    children: [
      {
        title: "Name",
        value: "project_name",
        align: "start",
        sortable: true,
        width: "18%",
        maxWidth: 220,
      },
      {
        title: "Version",
        value: "project_version",
        align: "start",
        sortable: true,
      },
    ],
  },
  { title: "Started", value: "run_started_at_ms", align: "center", sortable: true },
  { title: "Ended", value: "run_ended_at_ms", align: "center", sortable: true },
  { title: "Duration", key: "duration", align: "center", sortable: false },
  { title: "Status", value: "status", align: "start", sortable: true },
  { title: "Source", value: "source", align: "start", sortable: false },
  { title: "Attempt", value: "attempt_number", align: "start", sortable: false },
  { title: "Actions", key: "actions", align: "start", sortable: false },
];

function formatDuration(startedAtMs: number, endedAtMs: number | null): string {
  if (endedAtMs === null) return "—";
  const intTotalSeconds = Math.floor((endedAtMs - startedAtMs) / 1000);
  const intHours = Math.floor(intTotalSeconds / 3600);
  const intMinutes = Math.floor((intTotalSeconds % 3600) / 60);
  const intSeconds = intTotalSeconds % 60;
  return [intHours, intMinutes, intSeconds]
    .map((value) => String(value).padStart(2, "0"))
    .join(":");
}

function getStatusLabel(status: RunStatus): string {
  return DICT_RUN_STATUS_DISPLAY[status].title;
}

function getStatusColor(status: RunStatus): string {
  return DICT_RUN_STATUS_DISPLAY[status].color;
}

async function openLogFolder(runHistoryId: number): Promise<void> {
  try {
    await invokeMain("openRunLogFolder", runHistoryId);
  } catch (e: unknown) {
    loggerRenderer.error(`Failed to open Run log folder: ${getErrorMessage(e)}`);
  }
}

async function stopRun(historyId: number): Promise<void> {
  if (setPendingStop.value.has(historyId) || setStoppingRunId.value.has(historyId)) return;
  setPendingStop.value.add(historyId);
  try {
    await jobQueueStore.stopCurrentRun(historyId);
  } catch (e: unknown) {
    loggerRenderer.error(`Failed to stop Run ${historyId}: ${getErrorMessage(e)}`);
  } finally {
    setPendingStop.value.delete(historyId);
  }
}

async function openRerunDialog(runHistoryId: number): Promise<void> {
  if (setPendingRerun.value.has(runHistoryId)) return;
  setPendingRerun.value.add(runHistoryId);
  try {
    rerunPackage.value = await invokeMain("getLocalRerunPackage", runHistoryId);
  } catch (e: unknown) {
    loggerRenderer.error(`Failed to rerun Run ${runHistoryId}: ${getErrorMessage(e)}`);
  } finally {
    setPendingRerun.value.delete(runHistoryId);
  }
}

onBeforeMount(() => {
  void jobQueueStore.refreshJobQueue().catch((e: unknown) => {
    loggerRenderer.error(`Failed to load Job Queue: ${getErrorMessage(e)}`);
  });
});

onBeforeUnmount(() => {
  debouncedUpdateSearch.cancel();
  runHistoryStore.closeRunDetails();
});
</script>

<style scoped></style>
