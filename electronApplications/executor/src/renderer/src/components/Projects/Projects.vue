<!-- FileName: Projects.vue -->
<template>
  <v-container fluid class="clean-space flex-row-grow-1 fill-height flex-column">
    <v-label class="header-label tab-header">Projects</v-label>

    <v-container fluid class="pa-1 ma-0 flex-row" style="height: 45px">
      <v-btn
        variant="tonal"
        prepend-icon="mdi-package-variant-plus"
        @click="installProjectPackage()">
        Install Package
      </v-btn>
    </v-container>

    <!-- Main area -->
    <v-container fluid class="clean-space flex-column-grow-1 flex-row">
      <v-container
        fluid
        class="clean-space fill-height flex-column"
        style="flex: 0 0 30%; min-width: 0px">
        <v-label class="header-label column-header">Name</v-label>

        <!-- mandatory: After the first click, an item will always remain activated and cannot be deactivated -->
        <v-list
          v-if="projectStore.arrName.length !== 0"
          v-model:activated="arrSelectedName"
          :items="projectStore.arrName"
          item-value="value"
          class="clean-space w-100"
          style="width: max-content; flex: 1; min-width: 0px"
          activatable
          mandatory
          density="compact"
          variant="flat"
          @update:activated="clickNewProjectItem($event as string[])"></v-list>
      </v-container>

      <VerticalDivider />

      <v-container
        fluid
        class="clean-space fill-height flex-column"
        style="width: 120px; flex-shrink: 0">
        <v-label class="header-label column-header">Version</v-label>

        <!-- Add a v-if to remove the previous status of the list. -->
        <v-list
          v-if="projectStore.arrVersion.length !== 0"
          v-model:activated="arrSelectedVersion"
          :items="projectStore.arrVersion"
          item-value="value"
          class="clean-space w-100 flex-column-grow-1"
          style="width: max-content"
          activatable
          mandatory
          density="compact"
          variant="flat"
          @update:activated="clickNewVersionItem($event as string[])"></v-list>
      </v-container>

      <VerticalDivider />

      <v-container
        fluid
        class="clean-space fill-height flex-column"
        style="flex: 1; min-width: 0px">
        <v-label class="header-label column-header">Details</v-label>

        <!-- The data area. -->
        <v-container
          v-if="projectStore.dictDetailEdit"
          fluid
          class="clean-space flex-column flex-column-grow-1">
          <ProjectMetadata />

          <!-- The data can be modified. -->
          <!-- Due to the labels in v-text-field and other single labels are positioned differently, use pt, mt to align them consistently. -->
          <v-container fluid class="pa-2 ma-0 pt-0 flex-column-grow-1">
            <v-row class="clean-space fill-height">
              <!-- Left half -->
              <ProjectRunSettings v-if="projectStore.dictDetailEdit" />

              <!-- Right half: Custom Project Arguments -->
              <v-col cols="6" class="clean-space flex-column">
                <v-label class="clean-space" style="font-size: 0.75em">
                  Custom Arguments
                </v-label>

                <CustomArgumentsEditor
                  v-model:custom-args="projectStore.dictDetailEdit.custom_prj_args" />
              </v-col>
            </v-row>
          </v-container>
        </v-container>

        <!-- The button area. -->
        <v-container
          v-if="projectStore.dictDetailEdit"
          fluid
          class="pa-1 ma-0"
          style="height: 45px">
          <v-row class="clean-space w-100">
            <v-col cols="3" class="clean-space">
              <v-btn
                variant="tonal"
                prepend-icon="mdi-content-save-outline"
                :disabled="!boolDetailChanged"
                @click="saveProjectSettings()">
                Save
              </v-btn>
            </v-col>
            <v-col cols="3" class="clean-space">
              <v-btn
                variant="tonal"
                prepend-icon="mdi-content-save-off-outline"
                :disabled="!boolDetailChanged"
                @click="refreshDetail()">
                Cancel
              </v-btn>
            </v-col>
            <v-col cols="3" class="clean-space">
              <v-btn
                variant="tonal"
                prepend-icon="mdi-delete-empty-outline"
                @click="openDeleteDialog()">
                Delete
              </v-btn>
            </v-col>
            <v-col cols="3" class="clean-space">
              <v-btn
                variant="tonal"
                prepend-icon="mdi-play-outline"
                :disabled="boolDetailChanged"
                @click="runProject()">
                Run Now
              </v-btn>
            </v-col>
          </v-row>
        </v-container>

        <v-dialog v-model="boolShowRunDialog" max-width="800" persistent scrollable>
          <v-card v-if="runSettings" title="Run Now">
            <v-card-text>
              <v-select
                v-model="runSettings.python_environment_name"
                label="Python Environment"
                :items="projectStore.arrPythonEnvironmentName" />
              <BuiltInRunOptions
                v-model:retry-count="runSettings.retry_count"
                v-model:timeout-min="runSettings.timeout_min"
                v-model:log-level="runSettings.builtin_log_level"
                v-model:record-video="runSettings.builtin_record_video"
                v-model:stop-shortcut="runSettings.builtin_stop_shortcut"
                v-model:highlight-ui="runSettings.builtin_highlight_ui" />
              <CustomArgumentsEditor v-model:custom-args="runSettings.custom_prj_args" />
            </v-card-text>
            <v-card-actions>
              <v-spacer />
              <v-btn @click="boolShowRunDialog = false">Cancel</v-btn>
              <v-btn color="primary" @click="submitRun">Run</v-btn>
            </v-card-actions>
          </v-card>
        </v-dialog>

        <DeleteProjectDialog @deleted="resetProjectSelection" />
      </v-container>
    </v-container>
  </v-container>
</template>

<script setup lang="ts">
import DeleteProjectDialog from "./DeleteProjectDialog.vue";
import ProjectMetadata from "./ProjectMetadata.vue";
import ProjectRunSettings from "./ProjectRunSettings.vue";
import CustomArgumentsEditor from "../RunOptions/CustomArgumentsEditor.vue";
import BuiltInRunOptions from "../RunOptions/BuiltInRunOptions.vue";
import VerticalDivider from "../Common/VerticalDivider.vue";
import { cloneJsonSerializable } from "../../Common/json";
import type { Dict_ProjectSettingsUpdate } from "../../../../shared/project";

import { onBeforeMount, onBeforeUnmount, ref, watch } from "vue";
import { debounce } from "lodash";

import { invokeMain } from "../../IPC/ipc";
import { loggerRenderer } from "../../Logging/logger";
import { useProjectStore } from "../../Store/projectStore";
import { useRunHistoryStore } from "../../Store/runHistoryStore";

const projectStore = useProjectStore();
const runHistoryStore = useRunHistoryStore();
const boolShowRunDialog = ref(false);
const runSettings = ref<Dict_ProjectSettingsUpdate>();
async function submitRun(): Promise<void> {
  if (!runSettings.value) return;
  const detail = runSettings.value;
  await invokeMain("runProject", {
    id: detail.id,
    python_environment_name: detail.python_environment_name,
    retry_count: detail.retry_count,
    timeout_min: detail.timeout_min,
    builtin_log_level: detail.builtin_log_level,
    builtin_record_video: detail.builtin_record_video,
    builtin_stop_shortcut: detail.builtin_stop_shortcut,
    builtin_highlight_ui: detail.builtin_highlight_ui,
    custom_prj_args: cloneJsonSerializable(detail.custom_prj_args),
  });
  boolShowRunDialog.value = false;
  await runHistoryStore.refreshRunHistory();
}

const strName = ref("");
const strVersion = ref("");
const arrSelectedName = ref<string[]>([]);
const arrSelectedVersion = ref<string[]>([]);
const boolDetailChanged = ref(false);

onBeforeMount(async () => {
  projectStore.resetVersionAndDetail();
  await projectStore.loadProjectNames();
});

function resetProjectSelection(): void {
  strName.value = "";
  strVersion.value = "";
  arrSelectedName.value = [];
  arrSelectedVersion.value = [];
  boolDetailChanged.value = false;
}

async function installProjectPackage(): Promise<void> {
  loggerRenderer.debug("--installProjectPackage--");

  const result = await invokeMain("installProjectPackage");
  if (result.status === "canceled") {
    return;
  }

  projectStore.arrName = [];
  await projectStore.loadProjectNames();

  strName.value = result.name;
  arrSelectedName.value = [result.name];
  await projectStore.loadProjectVersions(result.name);

  strVersion.value = result.version;
  arrSelectedVersion.value = [result.version];

  await projectStore.loadProjectDetail(result.name, result.version);
}

const debouncedSetButtonDisabled = debounce(() => {
  // Changed name or version.
  if (!projectStore.dictDetailEdit) {
    boolDetailChanged.value = false;
    return;
  }

  const strDetailCacheNew = JSON.stringify(projectStore.dictDetailEdit);
  if (strDetailCacheNew === projectStore.strDetailCacheEdit) {
    boolDetailChanged.value = false;
  } else {
    boolDetailChanged.value = true;
  }
}, 300);

watch(
  () => projectStore.dictDetailEdit,
  () => {
    debouncedSetButtonDisabled();
  },
  { deep: true },
);

onBeforeUnmount(() => {
  debouncedSetButtonDisabled.cancel();
});

async function refreshDetail(): Promise<void> {
  projectStore.resetDetail();
  await projectStore.loadProjectDetail(strName.value, strVersion.value);
}

/* Click triggers */

async function clickNewProjectItem(arrName: string[]): Promise<void> {
  const strSelectedName = arrName[0];
  if (strSelectedName === undefined) {
    return;
  }

  strName.value = strSelectedName;
  strVersion.value = "";
  arrSelectedVersion.value = [];
  await projectStore.loadProjectVersions(strSelectedName);
}

async function clickNewVersionItem(arrVersion: string[]): Promise<void> {
  const strSelectedVersion = arrVersion[0];
  if (strSelectedVersion === undefined) {
    return;
  }

  strVersion.value = strSelectedVersion;
  await projectStore.loadProjectDetail(strName.value, strSelectedVersion);
}

async function saveProjectSettings(): Promise<void> {
  loggerRenderer.debug("--saveProjectSettings--");
  await projectStore.saveProjectSettings();
  await refreshDetail();
}

async function openDeleteDialog(): Promise<void> {
  const currentDetail = projectStore.dictDetailEdit;
  if (currentDetail !== undefined) {
    loggerRenderer.info(
      `Open delete dialog for project: ${currentDetail.id}-${currentDetail.name}-${currentDetail.version}`,
    );
    await projectStore.loadBoundSchedules();
    if (projectStore.dictDetailEdit === currentDetail) {
      projectStore.showDeleteDialog = true;
    }
  }
}

async function runProject(): Promise<void> {
  loggerRenderer.debug("--runProject--");
  if (projectStore.dictDetailEdit) {
    runSettings.value = cloneJsonSerializable(projectStore.dictDetailEdit);
    boolShowRunDialog.value = true;
  }
}
</script>

<style scoped></style>
