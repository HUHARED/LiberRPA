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
      @update:options="runHistoryStore.loadRunHistoryPage($event)">
      <template #item.project_source="{ value }">
        <v-chip
          :border="`${getProjectSourceColor(value)} thin opacity-25`"
          :color="getProjectSourceColor(value)"
          :text="value"
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
          <v-tooltip text="Open Log Folder" location="bottom">
            <template #activator="{ props }">
              <v-icon
                v-bind="props"
                color="medium-emphasis"
                icon="mdi-file-document-outline"
                size="small"
                @click="openLogFolder(item.log_path)">
              </v-icon>
            </template>
          </v-tooltip>

          <v-tooltip text="Cancel Run" location="bottom">
            <template #activator="{ props }">
              <v-icon
                v-if="item.status === 'running'"
                v-bind="props"
                color="medium-emphasis"
                icon="mdi-stop-circle-outline"
                size="small"
                @click="cancelProcess(item.id)">
              </v-icon>
            </template>
          </v-tooltip>

          <v-tooltip text="Run Latest Version" location="bottom">
            <template #activator="{ props }">
              <v-icon
                v-if="item.status !== 'running'"
                v-bind="props"
                color="medium-emphasis"
                icon="mdi-replay"
                size="small"
                @click="runProjectNewestVersion(item.project_source, item.project_name)">
              </v-icon>
            </template>
          </v-tooltip>
        </div>
      </template>

      <template #thead>
        <tr>
          <td>
            <v-text-field
              v-model="runHistoryStore.filterScheduleName"
              class="pa-0 ma-0 pl-2 pr-2"
              density="compact"
              hide-details
              variant="underlined">
            </v-text-field>
          </td>
          <td>
            <v-select
              v-model="runHistoryStore.filterSource"
              variant="underlined"
              class="pa-0 ma-0 pl-2 pr-2"
              density="compact"
              hide-details
              clearable
              :items="['local', 'console']">
            </v-select>
          </td>
          <td>
            <v-text-field
              v-model="runHistoryStore.filterProjectName"
              class="pa-0 ma-0 pl-2 pr-2"
              density="compact"
              hide-details
              variant="underlined">
            </v-text-field>
          </td>
          <td>
            <v-text-field
              v-model="runHistoryStore.filterProjectVersion"
              class="pa-0 ma-0 pl-2 pr-2"
              density="compact"
              hide-details
              variant="underlined">
            </v-text-field>
          </td>
          <td></td>
          <td></td>
          <td></td>
          <td>
            <v-select
              v-model="runHistoryStore.filterStatus"
              variant="underlined"
              class="pa-0 ma-0 pl-2 pr-2"
              density="compact"
              hide-details
              clearable
              :items="[
                { title: 'Running', value: 'running' },
                { title: 'Completed', value: 'completed' },
                { title: 'Error', value: 'error' },
                { title: 'Canceled', value: 'cancel' },
                { title: 'Timed Out', value: 'timeout' },
                { title: 'Interrupted', value: 'interrupted' },
              ]">
            </v-select>
          </td>
        </tr>
      </template>
    </v-data-table-server>
  </v-container>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { Ref } from "vue";
import { debounce } from "lodash";
import type { DataTableHeader } from "vuetify";

import { invokeMain } from "../IPC/ipc";
import { loggerRenderer } from "../Logging/logger";
import { getProjectSourceColor } from "../Common/display";
import { cloneJsonSerializable } from "../Common/json";
import { useRunHistoryStore } from "../Store/runHistoryStore";
import { useInformationStore } from "../Store/informationStore";
import { useSettingStore } from "../Store/settingStore";
import { formatTimestamp } from "../Common/time";
import type {
  TypeRunHistoryStatus,
  DictProjectRunDetail,
  DictColumns_RunHistory_ListItem_DB,
  DictRunHistorySearch,
} from "../../../shared/interface";

const runHistoryStore = useRunHistoryStore();
const settingStore = useSettingStore();

const itemPerPage: Ref<15 | 50 | 100> = ref(15);

const arrItemsPerPageOptions = [
  { value: 15, title: "15" },
  { value: 50, title: "50" },
  { value: 100, title: "100" },
];

const dictSearch = computed<DictRunHistorySearch>(() => {
  return {
    scheduler_name: runHistoryStore.filterScheduleName,
    project_source: runHistoryStore.filterSource,
    project_name: runHistoryStore.filterProjectName,
    project_version: runHistoryStore.filterProjectVersion,
    status: runHistoryStore.filterStatus,
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

const arrHeader: DataTableHeader<DictColumns_RunHistory_ListItem_DB>[] = [
  { title: "Schedule", value: "scheduler_name", align: "start", sortable: true },
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
  { title: "Actions", key: "actions", align: "start", sortable: false },
];

function getStatusLabel(status: TypeRunHistoryStatus): string {
  switch (status) {
    case "running":
      return "Running";
    case "completed":
      return "Completed";
    case "error":
      return "Error";
    case "cancel":
      return "Canceled";
    case "timeout":
      return "Timed Out";
    case "interrupted":
      return "Interrupted";
  }
}

function getStatusColor(status: TypeRunHistoryStatus): string {
  switch (status) {
    case "running":
      return "success";
    case "error":
      return "error";
    case "cancel":
      return "warning";
    case "timeout":
      return "orange-darken-4";
    case "interrupted":
      return "deep-orange";
    default:
      return "grey";
  }
}

async function openLogFolder(folderPath: string): Promise<void> {
  try {
    await invokeMain("openFolder", folderPath);
  } catch (e) {
    loggerRenderer.error(`Failed to open Run log folder: ${String(e)}`);
  }
}

async function cancelProcess(id: number): Promise<void> {
  loggerRenderer.info(`Cancel process: ${id}`);
  await invokeMain("pythonCancel", id);
}

async function runProjectNewestVersion(
  projectSource: "local" | "console",
  projectName: string,
): Promise<void> {
  loggerRenderer.info(`Run newest version: ${projectSource} ${projectName}`);

  if (projectSource !== "local") {
    return;
  }

  const dictDetail = await invokeMain("selectNewestProjectVersionDetail", projectName);
  if (dictDetail === undefined) {
    const informationStore = useInformationStore();
    informationStore.showAlertMessage("The project has been deleted.");
    return;
  }

  const dictRunDetail: DictProjectRunDetail = {
    schedule_name: null,
    project_source: "local",
    id: dictDetail.id,
    name: dictDetail.name,
    version: dictDetail.version,
    python_environment_name: dictDetail.python_environment_name,
    timeout_min: dictDetail.timeout_min,
    builtin_log_level: dictDetail.builtin_log_level,
    builtin_record_video: dictDetail.builtin_record_video === 1,
    builtin_stop_shortcut: dictDetail.builtin_stop_shortcut === 1,
    builtin_highlight_ui: dictDetail.builtin_highlight_ui === 1,
    custom_prj_args:
      dictDetail.custom_prj_args === "" ? [] : JSON.parse(dictDetail.custom_prj_args),
  };

  await invokeMain("pythonRun", cloneJsonSerializable(dictRunDetail));
  await runHistoryStore.refreshRunHistory();
}
</script>

<style scoped></style>
