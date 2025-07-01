<!-- FileName: TaskHistory.vue -->
<template>
  <v-container fluid class="clean-space flex-row-grow-1 fill-height flex-column">
    <v-label class="header-label tab-header">Task History</v-label>

    <!-- Table area -->

    <!-- Bug: The "hover" attribute will only work when the window is in the main screen. -->
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

      <template #item.run_start="{ value }">
        <v-chip :text="value" variant="text" size="small" class="clean-space"></v-chip>
      </template>

      <template #item.run_end="{ value }">
        <v-chip :text="value" variant="text" size="small" class="clean-space"></v-chip>
      </template>

      <template #item.status="{ value }">
        <v-chip
          :border="`${getColor_Status(value)} thin opacity-25`"
          :color="getColor_Status(value)"
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
              :items="['running', 'completed', 'error', 'cancel', 'timeout']">
            </v-select>
          </td>
        </tr>
      </template>
    </v-data-table-server>
  </v-container>
</template>

<script setup lang="ts">
import { ref, Ref, watch, computed } from "vue";
import { debounce } from "lodash";

import { invokeMain, loggerRenderer } from "../ipcOfRenderer";
import { getColor_Source, fileOpenFolder, sanitizeJsonObj } from "../commonFunc";
import { useHistoryStore, useInformationStore } from "../store";
import {
  DictColumns_Project_Detail_Run,
  DictColumns_Project_Detail_DB,
  Dict_History_Search,
} from "../../../shared/interface";

const historyStore = useHistoryStore();

const itemPerPage: Ref<15 | 50 | 100> = ref(15);

const arrItemsPerPageOptions = [
  { value: 15, title: "15" },
  { value: 50, title: "50" },
  { value: 100, title: "100" },
];

const dictSearch = computed<Dict_History_Search>({
  get() {
    return {
      scheduler_name: historyStore.filterSchedulerName,
      project_source: historyStore.filterSource,
      project_name: historyStore.filterProjectName,
      project_version: historyStore.filterProjectVersion,
      status: historyStore.filterStatus,
    };
  },
  set() {
    // Not work.
  },
});

const search = ref(JSON.stringify(dictSearch.value));

const debounced_WhenSearchFiltersChanged = debounce(async () => {
  search.value = JSON.stringify(dictSearch.value);
}, 300);

watch(
  () => dictSearch,
  () => {
    debounced_WhenSearchFiltersChanged();
  },
  { deep: true }
);

const arrHeader = [
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

  { title: "Start", value: "run_start", align: "center", sortable: true },
  { title: "End", value: "run_end", align: "center", sortable: true },

  { title: "Status", value: "status", align: "start", sortable: true },
  { title: "Actions", key: "actions", align: "start", sortable: false },
] as any; // use "as any" to make :headers in v-data-table not to complain.

function getColor_Status(
  status: "running" | "completed" | "error" | "cancel" | "timeout"
): string {
  switch (status) {
    case "running":
      return "success";
    case "error":
      return "error";

    case "cancel":
      return "warning";

    case "timeout":
      return "orange-darken-4";

    default:
      return "grey";
  }
}

async function cancelProcess(id: number): Promise<void> {
  loggerRenderer.info("cancelProcess: " + id);
  await invokeMain("invoke:pythonCancel", id);
}

async function runProjectNewestVersion(
  project_source: "local" | "console",
  project_name: string
): Promise<void> {
  loggerRenderer.info(`runProjectNewestVersion: ${project_source} ${project_name}`);

  if (project_source === "local") {
    const dictDetail: DictColumns_Project_Detail_DB = await invokeMain(
      "invoke:dbSelectProjectNewestVersionDetail",
      project_name
    );

    if (dictDetail) {
      const dictTemp: DictColumns_Project_Detail_Run = {
        scheduler_name: null,
        // Only "local" now.
        project_source: "local",
        id: dictDetail.id,
        name: dictDetail.name,
        version: dictDetail.version,
        timeout_min: dictDetail.timeout_min,
        buildin_log_level: dictDetail.buildin_log_level,
        buildin_record_video: dictDetail.buildin_record_video === 1,
        buildin_stop_shortcut: dictDetail.buildin_stop_shortcut === 1,
        buildin_highlight_ui: dictDetail.buildin_highlight_ui === 1,
        custom_prj_args: dictDetail.custom_prj_args
          ? JSON.parse(dictDetail.custom_prj_args)
          : [],
      };

      await invokeMain("invoke:pythonRun", sanitizeJsonObj(dictTemp));
      await historyStore.refreshHistoryList();
    } else {
      const informationStore = useInformationStore();
      informationStore.showAlertMessage("The project has been deleted.");
    }
  } else {
    // Only local now.
  }
}
</script>

<style scoped></style>
