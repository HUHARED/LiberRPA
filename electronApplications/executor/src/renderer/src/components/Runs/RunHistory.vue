<!-- FileName: RunHistory.vue -->
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
        {{ DICT_RUN_SOURCE_LABEL[item.source] }}
      </template>

      <template #item.run_started_at_ms="{ value }">
        <v-chip
          :text="formatTimestamp(value, settingStore.timezone)"
          variant="text"
          size="small"
          class="clean-space"></v-chip>
      </template>

      <template #item.run_ended_at_ms="{ value }">
        <v-chip
          :text="formatTimestamp(value, settingStore.timezone)"
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
        <div class="d-flex ga-2 justify-start">
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

          <v-tooltip
            v-if="item.status === RunStatus.Running"
            text="Stop Run"
            location="bottom"
            :open-on-focus="false">
            <template #activator="{ props }">
              <v-icon
                v-bind="props"
                color="medium-emphasis"
                icon="mdi-stop-circle-outline"
                size="small"
                @click="cancelProcess(item.id)"></v-icon>
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

    <RunProjectDialog
      v-if="rerunProject"
      :project="rerunProject"
      @close="rerunProject = undefined" />

    <v-dialog v-model="boolShowDetails" max-width="850" height="80vh" persistent scrollable>
      <v-card v-if="runDetails" title="Run Details">
        <v-card-text class="flex-column overflow-hidden">
          <div class="flex-shrink-0">
            {{ DICT_RUN_SOURCE_LABEL[runDetails.source] }} · Attempt
            {{ runDetails.attempt_number }}
          </div>

          <div v-if="runDetails.source === RunSource.Console" class="flex-shrink-0">
            Job {{ runDetails.job_id }}
          </div>

          <div class="flex-column flex-column-grow-1 overflow-hidden">
            <h3 class="mt-3 flex-shrink-0">Inputs</h3>

            <pre class="flex-column-grow-1 text-pre-wrap text-break">{{
              JSON.stringify(runDetails.snapshot, null, 2)
            }}</pre>
          </div>

          <div class="flex-column flex-column-grow-1 overflow-hidden">
            <h3 class="mt-3 flex-shrink-0">Outputs — {{ runDetails.outputs.status }}</h3>

            <div class="flex-column-grow-1">
              <v-alert v-if="runDetails.outputs.reason" variant="tonal" class="my-2">
                {{ runDetails.outputs.reason }}
              </v-alert>

              <pre class="text-pre-wrap text-break">{{
                JSON.stringify(runDetails.outputs.values, null, 2)
              }}</pre>

              <div v-if="runDetails.outputs.unavailableKeys.length" class="text-break">
                Unavailable: {{ runDetails.outputs.unavailableKeys.join(", ") }}
              </div>

              <v-alert v-if="runDetails.error_summary" type="error" variant="tonal">
                {{ runDetails.error_summary.type }}:
                {{ runDetails.error_summary.message }}
              </v-alert>
            </div>
          </div>
        </v-card-text>

        <v-card-actions>
          <v-btn variant="tonal" prepend-icon="mdi-close" @click="boolShowDetails = false">
            Close
          </v-btn>
          <v-spacer />
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch, type Ref } from "vue";
import { debounce } from "lodash";
import type { DataTableHeader } from "vuetify";

import RunProjectDialog from "../Projects/RunProjectDialog.vue";

import type { ProjectDetails } from "../../../../shared/project";

import { getErrorMessage } from "../../../../shared/error";
import {
  RunSource,
  type RunDetails,
  RunStatus,
  type RunHistoryItem,
  type RunHistoryFilters,
  type RunHistoryQueryOptions,
} from "../../../../shared/run";

import { invokeMain } from "../../IPC/ipc";
import { loggerRenderer } from "../../Logging/logger";
import { cloneJsonSerializable } from "../../Common/json";
import { useRunHistoryStore } from "../../Store/runHistoryStore";
import { useSettingStore } from "../../Store/settingStore";
import { formatTimestamp } from "../../Common/time";

const DICT_RUN_SOURCE_LABEL: Record<RunSource, string> = {
  [RunSource.Local]: "Local",
  [RunSource.Console]: "Console",
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
const settingStore = useSettingStore();

const boolShowDetails = ref(false);
const runDetails = ref<RunDetails>();
const setPendingRerun = ref(new Set<number>());
const rerunProject = ref<ProjectDetails>();

async function showRunDetails(id: number): Promise<void> {
  runDetails.value = await invokeMain("getRunDetails", id);
  boolShowDetails.value = true;
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

onBeforeUnmount(() => {
  debouncedUpdateSearch.cancel();
});

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

async function cancelProcess(id: number): Promise<void> {
  loggerRenderer.info(`Cancel process: ${id}`);
  await invokeMain("pythonCancel", id);
}

async function openRerunDialog(runHistoryId: number): Promise<void> {
  if (setPendingRerun.value.has(runHistoryId)) return;
  setPendingRerun.value.add(runHistoryId);
  try {
    rerunProject.value = await invokeMain("getLocalRerunProject", runHistoryId);
  } catch (e: unknown) {
    loggerRenderer.error(`Failed to rerun Run ${runHistoryId}: ${getErrorMessage(e)}`);
  } finally {
    setPendingRerun.value.delete(runHistoryId);
  }
}
</script>

<style scoped></style>
