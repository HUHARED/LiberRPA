<template>
  <v-container fluid class="clean-space flex-row-grow-1 fill-height flex-column">
    <v-label class="header-label tab-header">Projects</v-label>

    <v-container fluid class="pa-1 ma-0 flex-row" style="height: 45px">
      <v-btn
        variant="tonal"
        prepend-icon="mdi-database-import-outline"
        @click="importProjectPackage()">
        Import Package
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
          :items="projectStore.arrName"
          item-value="idTemp"
          class="clean-space w-100"
          style="width: max-content; flex: 1; min-width: 0px"
          activatable
          mandatory
          density="compact"
          variant="flat"
          @update:activated="clickNewProjectItem($event as number[])">
        </v-list>
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
          :items="projectStore.arrVersion"
          item-value="idTemp"
          class="clean-space w-100 flex-column-grow-1"
          style="width: max-content"
          activatable
          mandatory
          density="compact"
          variant="flat"
          @update:activated="clickNewVersionItem($event as number[])"></v-list>
      </v-container>

      <VerticalDivider />

      <v-container
        fluid
        class="clean-space fill-height flex-column"
        style="flex: 1; min-width: 0px">
        <v-label class="header-label column-header"> Details </v-label>

        <!-- The data area. -->
        <v-container
          v-if="projectStore.dictDetail_edit"
          fluid
          class="clean-space flex-column flex-column-grow-1">
          <ProjectMetadata />

          <!-- The data can be modified. -->
          <!-- Due to the labels in v-text-field and other single labels are positioned differently, use pt, mt to align them consistently. -->
          <v-container fluid class="pa-2 ma-0 pt-0 flex-column-grow-1">
            <v-row class="clean-space fill-height">
              <!-- Left half -->
              <ProjectRunSettings v-if="projectStore.dictDetail_edit" />

              <!-- Right half: Custom Project Arguments -->
              <v-col cols="6" class="clean-space flex-column">
                <v-label class="clean-space" style="font-size: 0.75em">
                  Custom Arguments
                </v-label>

                <CustomArgumentsEditor
                  v-model:custom-args="projectStore.dictDetail_edit.custom_prj_args" />
              </v-col>
            </v-row>
          </v-container>
        </v-container>

        <!-- The button area. -->
        <v-container
          v-if="projectStore.dictDetail_edit"
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

        <DeleteProjectDialog />
      </v-container>
    </v-container>
  </v-container>
</template>

<script setup lang="ts">
import DeleteProjectDialog from "./DeleteProjectDialog.vue";
import ProjectMetadata from "./ProjectMetadata.vue";
import ProjectRunSettings from "./ProjectRunSettings.vue";
import CustomArgumentsEditor from "../RunOptions/CustomArgumentsEditor.vue";
import VerticalDivider from "../Common/VerticalDivider.vue";

import { onBeforeMount, onBeforeUnmount, ref, watch } from "vue";
import { debounce } from "lodash";

import { invokeMain } from "../../IPC/ipc";
import { loggerRenderer } from "../../Logging/logger";
import { useProjectStore } from "../../Store/projectStore";
import { useRunHistoryStore } from "../../Store/runHistoryStore";

const projectStore = useProjectStore();
const runHistoryStore = useRunHistoryStore();

const strName = ref("");
const strVersion = ref("");
const boolDetailChanged = ref(false);

onBeforeMount(async () => {
  projectStore.resetVersionAndDetail();
  await projectStore.loadProjectNames();
});

async function importProjectPackage(): Promise<void> {
  loggerRenderer.debug("--importProjectPackage--");

  const result = await invokeMain("importProjectPackage");
  if (result.status === "canceled") {
    return;
  }

  projectStore.arrName = [];
  await projectStore.loadProjectNames();
  strName.value = result.name;
  await projectStore.loadProjectVersions(result.name);
  strVersion.value = result.version;
  await projectStore.loadProjectDetail(result.name, result.version);
}

const debouncedSetButtonDisabled = debounce(() => {
  // Changed name or version.
  if (!projectStore.dictDetail_edit) {
    boolDetailChanged.value = false;
    return;
  }

  const strDetailCacheNew = JSON.stringify(projectStore.dictDetail_edit);
  if (strDetailCacheNew === projectStore.detailCache_edit) {
    boolDetailChanged.value = false;
  } else {
    boolDetailChanged.value = true;
  }
}, 300);

watch(
  () => projectStore.dictDetail_edit,
  () => {
    debouncedSetButtonDisabled();
  },
  { deep: true },
);

onBeforeUnmount(() => {
  debouncedSetButtonDisabled.cancel();
});

async function refreshDetail(): Promise<void> {
  // loggerRenderer.debug("--refreshDetail--");
  projectStore.resetDetail();
  await projectStore.loadProjectDetail(strName.value, strVersion.value);
}

/* Click triggers */

async function clickNewProjectItem(arrId: number[]): Promise<void> {
  strName.value = projectStore.dictIdToName[arrId[0]];
  await projectStore.loadProjectVersions(strName.value);
}

async function clickNewVersionItem(arrId: number[]): Promise<void> {
  strVersion.value = projectStore.dictIdToVersion[arrId[0]];
  await projectStore.loadProjectDetail(strName.value, strVersion.value);
}

async function saveProjectSettings(): Promise<void> {
  loggerRenderer.debug("--saveProjectSettings--");
  await projectStore.saveProjectSettings();
  await refreshDetail();
}

async function openDeleteDialog(): Promise<void> {
  if (projectStore.dictDetail_edit) {
    loggerRenderer.info(
      `Open delete dialog for project: ${projectStore.dictDetail_edit.id}-${projectStore.dictDetail_edit.name}-${projectStore.dictDetail_edit.version}`,
    );
    await projectStore.loadBoundSchedules();
    projectStore.showDialog_delete = true;
  }
}

async function runProject(): Promise<void> {
  loggerRenderer.debug("--runProject--");
  if (projectStore.dictDetail_edit) {
    await invokeMain("runProject", projectStore.dictDetail_edit.id);
    await runHistoryStore.refreshRunHistory();
  }
}
</script>

<style scoped></style>
