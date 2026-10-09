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
          <v-icon
            icon="mdi-information-outline"
            size="small"
            title="Inputs and Outputs"
            @click="showRunDetails(item.id)" />

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
            text="Stop Current Run"
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
            v-else-if="item.source === RunSource.Local"
            text="Run Most Recently Installed Version"
            location="bottom"
            :open-on-focus="false">
            <template #activator="{ props }">
              <v-icon
                v-bind="props"
                color="medium-emphasis"
                icon="mdi-replay"
                size="small"
                @click="runMostRecentlyInstalledProjectVersion(item.project_name)"></v-icon>
            </template>
          </v-tooltip>

          <v-tooltip
            v-if="item.source === RunSource.Console"
            :text="
              item.console_run_url
                ? 'Open in Console'
                : 'The original Console address is unavailable.'
            "
            location="bottom"
            :open-on-focus="false">
            <template #activator="{ props }">
              <span v-bind="props">
                <v-btn
                  :href="item.console_run_url ?? undefined"
                  :disabled="item.console_run_url === null"
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label="Open in Console"
                  icon="mdi-open-in-new"
                  variant="text"
                  size="x-small" />
              </span>
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

    <v-dialog v-model="boolShowDetails" max-width="850" persistent scrollable>
      <v-card v-if="runDetails" title="Run Details">
        <v-card-text>
          <div>
            {{ DICT_RUN_SOURCE_LABEL[runDetails.source] }} · Attempt
            {{ runDetails.attempt }}
          </div>
          <div v-if="runDetails.source === RunSource.Console">
            Job {{ runDetails.job_id }}
          </div>
          <h3 class="mt-3">Inputs</h3>
          <pre class="text-wrap">{{ JSON.stringify(runDetails.inputs, null, 2) }}</pre>
          <h3 class="mt-3">Outputs — {{ runDetails.outputs.status }}</h3>
          <v-alert v-if="runDetails.outputs.reason" variant="tonal" class="my-2">
            {{ runDetails.outputs.reason }}
          </v-alert>
          <p
            v-if="
              runDetails.outputs.status === 'complete' && !runDetails.outputs.values?.length
            ">
            No output items.
          </p>
          <v-table v-else-if="runDetails.outputs.values?.length">
            <thead>
              <tr>
                <th>Key</th>
                <th>Value</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="[key, value] in runDetails.outputs.values" :key="key">
                <td>{{ key }}</td>
                <td>
                  <pre class="text-pre-wrap text-break py-2">{{
                    JSON.stringify(value, null, 2)
                  }}</pre>
                </td>
              </tr>
            </tbody>
          </v-table>
          <div v-if="runDetails.outputs.unavailableKeys.length">
            Unavailable: {{ runDetails.outputs.unavailableKeys.join(", ") }}
          </div>
          <v-alert v-if="runDetails.error_summary" type="error" variant="tonal">
            {{ runDetails.error_summary.type }}:
            {{ runDetails.error_summary.message }}
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-btn
            v-if="runDetails.source === RunSource.Console && runDetails.console_run_url"
            :href="runDetails.console_run_url"
            target="_blank"
            rel="noopener noreferrer"
            prepend-icon="mdi-open-in-new">
            Open in Console
          </v-btn>
          <v-spacer />
          <v-btn @click="boolShowDetails = false">Close</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import type { Ref } from "vue";
import { debounce } from "lodash";
import type { DataTableHeader } from "vuetify";

import { invokeMain } from "../../IPC/ipc";
import { loggerRenderer } from "../../Logging/logger";
import { cloneJsonSerializable } from "../../Common/json";
import { useRunHistoryStore } from "../../Store/runHistoryStore";
import { useSettingStore } from "../../Store/settingStore";
import { formatTimestamp } from "../../Common/time";
import { getErrorMessage } from "../../../../shared/error";
import {
  RunSource,
  RunStatus,
  type RunDetails,
  type Dict_RunHistory_Item,
  type Dict_RunHistory_Options,
  type Dict_RunHistory_Search,
} from "../../../../shared/run";

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

const dictSearch = computed<Dict_RunHistory_Search>(() => {
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

type Dict_RunHistory_Options_Table = Omit<Dict_RunHistory_Options, "search"> & {
  search: string;
};

async function handleTableOptionsUpdate(
  optionsDict: Dict_RunHistory_Options_Table,
): Promise<void> {
  await runHistoryStore.loadRunHistoryPage({
    page: optionsDict.page,
    itemsPerPage: optionsDict.itemsPerPage,
    sortBy: cloneJsonSerializable(optionsDict.sortBy),
    search: cloneJsonSerializable(dictSearch.value),
  });
}

const arrHeader: DataTableHeader<Dict_RunHistory_Item>[] = [
  { title: "Schedule", value: "schedule_name", align: "start", sortable: true },
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
      {
        title: "Environment",
        value: "python_environment_name",
        align: "start",
        sortable: true,
      },
    ],
  },
  { title: "Started", value: "run_started_at_ms", align: "center", sortable: true },
  { title: "Ended", value: "run_ended_at_ms", align: "center", sortable: true },
  { title: "Status", value: "status", align: "start", sortable: true },
  { title: "Source", value: "source", align: "start", sortable: false },
  { title: "Attempt", value: "attempt", align: "start", sortable: false },
  { title: "Actions", key: "actions", align: "start", sortable: false },
];

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

async function runMostRecentlyInstalledProjectVersion(projectName: string): Promise<void> {
  loggerRenderer.info(`Run most recently installed version: ${projectName}`);

  await invokeMain("runMostRecentlyInstalledProjectVersion", projectName);
  await runHistoryStore.refreshRunHistory();
}
</script>

<style scoped></style>
