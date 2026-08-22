<!-- FileName: TaskHistory.vue -->
<template>
  <v-container fluid class="clean-space flex-row-grow-1 fill-height flex-column">
    <v-label class="header-label tab-header">Task History</v-label>

    <!-- Bug: The hover attribute only works when the window is on the primary screen. -->
    <v-data-table-server
      :headers="arrHeader"
      :items="historyStore.arrListItem"
      :items-length="historyStore.itemLength"
      :items-per-page="itemPerPage"
      :items-per-page-options="arrItemsPerPageOptions"
      :search="search"
      class="clean-space flex-column-grow-1"
      fixed-header
      density="compact"
      hover
      multi-sort
      @update:options="historyStore.dbSelectLimitHistoryList($event)">
      <template #item.project_source="{ value }">
        <v-chip
          :border="`${getColor_Source(value)} thin opacity-25`"
          :color="getColor_Source(value)"
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
          :border="`${getColorStatus(value)} thin opacity-25`"
          :color="getColorStatus(value)"
          :text="value"
          variant="text"
          size="x-small"></v-chip>
      </template>

      <template #item.actions="{ item }">
        <div class="d-flex ga-2 justify-start">
          <v-tooltip text="Open its log folder." location="bottom">
            <template #activator="{ props }">
              <v-icon
                v-bind="props"
                color="medium-emphasis"
                icon="mdi-file-document-outline"
                size="small"
                @click="fileOpenFolder(item.log_path)">
              </v-icon>
            </template>
          </v-tooltip>

          <v-tooltip text="Cancel it." location="bottom">
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

          <v-tooltip text="Re-run the newest version." location="bottom">
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
              v-model="historyStore.filterSchedulerName"
              class="pa-0 ma-0 pl-2 pr-2"
              density="compact"
              hide-details
              variant="underlined">
            </v-text-field>
          </td>
          <td>
            <v-select
              v-model="historyStore.filterSource"
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
              v-model="historyStore.filterProjectName"
              class="pa-0 ma-0 pl-2 pr-2"
              density="compact"
              hide-details
              variant="underlined">
            </v-text-field>
          </td>
          <td>
            <v-text-field
              v-model="historyStore.filterProjectVersion"
              class="pa-0 ma-0 pl-2 pr-2"
              density="compact"
              hide-details
              variant="underlined">
            </v-text-field>
          </td>
          <td></td>
          <td></td>
          <td>
            <v-select
              v-model="historyStore.filterStatus"
              variant="underlined"
              class="pa-0 ma-0 pl-2 pr-2"
              density="compact"
              hide-details
              clearable
              :items="[
                'running',
                'completed',
                'error',
                'cancel',
                'timeout',
                'interrupted',
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

import { invokeMain, loggerRenderer } from "../ipcOfRenderer";
import { fileOpenFolder, getColor_Source, sanitizeJsonObj } from "../commonFunc";
import { useHistoryStore, useInformationStore, useSettingStore } from "../store";
import { formatTimestamp } from "../time";
import type {
  DictColumns_History_ListItem_DB,
  DictColumns_Project_Detail_DB,
  DictColumns_Project_Detail_Run,
  Dict_History_Search,
  TypeTaskHistoryStatus,
} from "../../../shared/interface";

const historyStore = useHistoryStore();
const settingStore = useSettingStore();

const itemPerPage: Ref<15 | 50 | 100> = ref(15);

const arrItemsPerPageOptions = [
  { value: 15, title: "15" },
  { value: 50, title: "50" },
  { value: 100, title: "100" },
];

const dictSearch = computed<Dict_History_Search>(() => {
  return {
    scheduler_name: historyStore.filterSchedulerName,
    project_source: historyStore.filterSource,
    project_name: historyStore.filterProjectName,
    project_version: historyStore.filterProjectVersion,
    status: historyStore.filterStatus,
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

const arrHeader: DataTableHeader<DictColumns_History_ListItem_DB>[] = [
  { title: "Scheduler Name", value: "scheduler_name", align: "start", sortable: true },
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
  { title: "Start", value: "run_started_at_ms", align: "center", sortable: true },
  { title: "End", value: "run_ended_at_ms", align: "center", sortable: true },
  { title: "Status", value: "status", align: "start", sortable: true },
  { title: "Actions", key: "actions", align: "start", sortable: false },
];

function getColorStatus(status: TypeTaskHistoryStatus): string {
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

async function cancelProcess(id: number): Promise<void> {
  loggerRenderer.info(`Cancel process: ${id}`);
  await invokeMain<void>("invoke:pythonCancel", id);
}

async function runProjectNewestVersion(
  projectSource: "local" | "console",
  projectName: string,
): Promise<void> {
  loggerRenderer.info(`Run newest version: ${projectSource} ${projectName}`);

  if (projectSource !== "local") {
    return;
  }

  const dictDetail = await invokeMain<DictColumns_Project_Detail_DB | undefined>(
    "invoke:dbSelectProjectNewestVersionDetail",
    projectName,
  );
  if (dictDetail === undefined) {
    const informationStore = useInformationStore();
    informationStore.showAlertMessage("The project has been deleted.");
    return;
  }

  const dictRunDetail: DictColumns_Project_Detail_Run = {
    scheduler_name: null,
    project_source: "local",
    id: dictDetail.id,
    name: dictDetail.name,
    version: dictDetail.version,
    timeout_min: dictDetail.timeout_min,
    builtin_log_level: dictDetail.builtin_log_level,
    builtin_record_video: dictDetail.builtin_record_video === 1,
    builtin_stop_shortcut: dictDetail.builtin_stop_shortcut === 1,
    builtin_highlight_ui: dictDetail.builtin_highlight_ui === 1,
    custom_prj_args:
      dictDetail.custom_prj_args === "" ? [] : JSON.parse(dictDetail.custom_prj_args),
  };

  await invokeMain<void>("invoke:pythonRun", sanitizeJsonObj(dictRunDetail));
  await historyStore.refreshHistoryList();
}
</script>

<style scoped></style>
