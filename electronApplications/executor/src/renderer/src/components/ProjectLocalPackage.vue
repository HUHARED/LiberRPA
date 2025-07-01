<!-- FileName: ProjectLocalPackage.vue -->
<template>
  <v-container fluid class="clean-space flex-row-grow-1 fill-height flex-column">
    <v-label class="header-label tab-header">Project Local Package</v-label>

    <v-container fluid class="pa-1 ma-0 flex-row" style="height: 45px">
      <v-btn
        variant="tonal"
        prepend-icon="mdi-database-import-outline"
        @click="importProjectPackage()">
        Import
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
        <v-label class="header-label column-header"> Detail </v-label>

        <!-- The data area. -->
        <v-container
          v-if="projectStore.dictDetail_edit"
          fluid
          class="clean-space flex-column flex-column-grow-1">
          <ProjectLocalPackage_Detail_Uneditable />

          <!-- The data can be modified. -->
          <!-- Due to the labels in v-text-field and other single labels are positioned differently, use pt, mt to align them consistently. -->
          <v-container fluid class="pa-2 ma-0 pt-0 flex-column-grow-1">
            <v-row class="clean-space fill-height">
              <!-- Left half -->
              <!-- Use v-if to make the intTimeoutMin in ProjectLocalPackage_Detail_BuildinArgs can be recreated. -->
              <ProjectLocalPackage_Detail_BuildinArgs v-if="projectStore.dictDetail_edit" />

              <!-- Right half: Custom Project Arguments -->
              <v-col cols="6" class="clean-space flex-column">
                <v-label class="clean-space" style="font-size: 0.75em">
                  Custom Project Arguments
                </v-label>

                <ProjectLocalPackage_Detail_CusPrjArgs />
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
                @click="dbUpdateProjectDetail()">
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
                Run
              </v-btn>
            </v-col>
          </v-row>
        </v-container>

        <ProjectLocalPackage_Dialog_Delete />
      </v-container>
    </v-container>
  </v-container>
</template>

<script setup lang="ts">
import ProjectLocalPackage_Detail_Uneditable from "./ProjectLocalPackage_Detail_Uneditable.vue";
import ProjectLocalPackage_Dialog_Delete from "./ProjectLocalPackage_Dialog_Delete.vue";
import ProjectLocalPackage_Detail_BuildinArgs from "./ProjectLocalPackage_Detail_BuildinArgs.vue";
import ProjectLocalPackage_Detail_CusPrjArgs from "./ProjectLocalPackage_Detail_CusPrjArgs.vue";
import VerticalDivider from "./utils/VerticalDivider.vue";

import { ref, watch, onBeforeMount } from "vue";
import { debounce } from "lodash";

import { loggerRenderer, invokeMain } from "../ipcOfRenderer";
import { useProjectStore, useInformationStore, useHistoryStore } from "../store";
import { sanitizeJsonObj } from "../commonFunc";
import {
  DictInvokeResult,
  DictColumns_Project_Detail_ToInsert,
  DictColumns_Project_Detail_Run,
} from "../../../shared/interface";

const projectStore = useProjectStore();
const informationStore = useInformationStore();
const historyStore = useHistoryStore();

const strName = ref("");
const strVersion = ref("");
const boolDetailChanged = ref(false);

onBeforeMount(async () => {
  projectStore.resetVersionAndDetail();
  await projectStore.dbSelectProjectNames();
});

async function importProjectPackage(): Promise<void> {
  loggerRenderer.debug("--importProjectPackage--");

  const dataExtract: DictColumns_Project_Detail_ToInsert | string = await invokeMain(
    "invoke:fileSelectPackageAndExtractToTempFolder"
  );
  if (typeof dataExtract === "string") {
    await invokeMain("invoke:fileDeleteTempFolder");
    informationStore.showAlertMessage(dataExtract);
    return;
  }

  const dataCheck: DictInvokeResult = await invokeMain("invoke:dbSelectProjectDetail", {
    name: dataExtract["name"],
    version: dataExtract["version"],
  });

  // console.log("dataCheck", dataCheck);

  if (dataCheck !== undefined) {
    informationStore.showAlertMessage(
      `${dataExtract["name"]}-${dataExtract["name"]} already exists.`
    );
    await invokeMain("invoke:fileDeleteTempFolder");
    return;
  }

  await invokeMain("invoke:fileMoveTempFilesToExecutorPackage", {
    name: dataExtract["name"],
    version: dataExtract["version"],
  });

  await projectStore.dbInsertProjectDetail(dataExtract);
}

const debounced_SetButtonDisabled = debounce(() => {
  // Changed name or version.
  if (!projectStore.dictDetail_edit) {
    boolDetailChanged.value = false;
    return;
  }

  // console.log("Update" + JSON.stringify(projectStore.dictDetail_edit));

  const strDetailCacheNew = JSON.stringify(projectStore.dictDetail_edit);
  if (strDetailCacheNew === projectStore.detailCache_edit) {
    // console.log("Set false");

    boolDetailChanged.value = false;
  } else {
    // console.log("Set true");

    boolDetailChanged.value = true;
  }
}, 300);

watch(
  () => projectStore.dictDetail_edit,
  () => {
    // console.log("!!update");

    debounced_SetButtonDisabled();
  },
  { deep: true }
);

async function refreshDetail(): Promise<void> {
  // loggerRenderer.debug("--refreshDetail--");
  projectStore.resetDetail();
  await projectStore.dbSelectProjectDetail(strName.value, strVersion.value);
}

/* Click triggers */

async function clickNewProjectItem(arrId: number[]): Promise<void> {
  // console.log("arrId-name", arrId);
  strName.value = projectStore.dictIdToName[arrId[0]];
  await projectStore.dbSelectProjectVersions(strName.value);
}

async function clickNewVersionItem(arrId: number[]): Promise<void> {
  // console.log("arrId-version", arrId);

  strVersion.value = projectStore.dictIdToVersion[arrId[0]];
  await projectStore.dbSelectProjectDetail(strName.value, strVersion.value);
}

async function dbUpdateProjectDetail(): Promise<void> {
  loggerRenderer.debug("--dbUpdateProjectDetail--");
  await projectStore.dbUpdateProjectDetail();
  await refreshDetail();
}

async function openDeleteDialog(): Promise<void> {
  if (projectStore.dictDetail_edit) {
    loggerRenderer.info(
      `Open delete dialog for project: ${projectStore.dictDetail_edit.id}-${projectStore.dictDetail_edit.name}-${projectStore.dictDetail_edit.version}`
    );
    await projectStore.dbSelectProjectBindSchedulers();
    projectStore.showDialog_delete = true;
  }
}

async function runProject(): Promise<void> {
  loggerRenderer.debug("--runProject--");
  if (projectStore.dictDetail_edit) {
    const dictTemp: DictColumns_Project_Detail_Run = {
      scheduler_name: null,
      // Only "local" now.
      project_source: "local",
      id: projectStore.dictDetail_edit.id,
      name: projectStore.dictDetail_edit.name,
      version: projectStore.dictDetail_edit.version,
      timeout_min: projectStore.dictDetail_edit.timeout_min,
      buildin_log_level: projectStore.dictDetail_edit.buildin_log_level,
      buildin_record_video: projectStore.dictDetail_edit.buildin_record_video,
      buildin_stop_shortcut: projectStore.dictDetail_edit.buildin_stop_shortcut,
      buildin_highlight_ui: projectStore.dictDetail_edit.buildin_highlight_ui,
      custom_prj_args: projectStore.dictDetail_edit.custom_prj_args,
    };

    await invokeMain("invoke:pythonRun", sanitizeJsonObj(dictTemp));
    await historyStore.refreshHistoryList();
  }
}
</script>

<style scoped></style>
