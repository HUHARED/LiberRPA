<!-- FileName: PackagesView.vue -->
<template>
  <v-container fluid class="clean-space flex-row-grow-1 fill-height flex-column">
    <v-label class="header-label tab-header">Packages</v-label>

    <v-container fluid class="pa-1 ma-0 flex-row" style="height: 45px">
      <v-spacer />
      <v-btn
        variant="tonal"
        prepend-icon="mdi-package-variant-plus"
        @click="installPackage()">
        Install Package
      </v-btn>
    </v-container>

    <!-- Main area -->
    <v-container fluid class="clean-space flex-column-grow-1 flex-row">
      <v-container
        fluid
        class="clean-space fill-height flex-column"
        style="flex: 0 0 30%; min-width: 0px">
        <v-label class="header-label column-header">Project Name</v-label>

        <!-- mandatory: After the first click, an item will always remain activated and cannot be deactivated -->
        <v-list
          v-if="packageStore.arrProjectName.length !== 0"
          v-model:activated="arrSelectedProjectName"
          :items="packageStore.arrProjectName"
          item-value="value"
          class="clean-space w-100"
          style="width: max-content; flex: 1; min-width: 0px"
          activatable
          mandatory
          density="compact"
          variant="flat"
          @update:activated="clickNewProjectItem($event as string[])"></v-list>
      </v-container>

      <v-divider vertical />

      <v-container
        fluid
        class="clean-space fill-height flex-column"
        style="width: 192px; flex-shrink: 0">
        <v-label class="header-label column-header">Project Version</v-label>

        <!-- Add a v-if to remove the previous status of the list. -->
        <v-list
          v-if="packageStore.arrProjectVersion.length !== 0"
          v-model:activated="arrSelectedProjectVersion"
          :items="packageStore.arrProjectVersion"
          item-value="value"
          class="clean-space w-100 flex-column-grow-1"
          style="width: max-content"
          activatable
          mandatory
          density="compact"
          variant="flat"
          @update:activated="clickNewProjectVersionItem($event as string[])"></v-list>
      </v-container>

      <v-divider vertical />

      <v-container
        fluid
        class="clean-space fill-height flex-column"
        style="flex: 1; min-width: 0px">
        <v-label class="header-label column-header">Package Details</v-label>

        <!-- The data area. -->
        <v-container
          v-if="packageStore.dictDetailEdit"
          fluid
          class="clean-space flex-column flex-column-grow-1">
          <PackageDetails />

          <!-- The data can be modified. -->
          <!-- Due to the labels in v-text-field and other single labels are positioned differently, use pt, mt to align them consistently. -->
          <v-container fluid class="pa-2 ma-0 pt-0 flex-column-grow-1">
            <v-row class="clean-space fill-height">
              <!-- Left half -->
              <PackageRunSettings v-if="packageStore.dictDetailEdit" />

              <!-- Right half: Custom Project Arguments -->
              <v-col cols="6" class="clean-space flex-column">
                <v-label class="clean-space" style="font-size: 0.75em">
                  Custom Project Arguments
                </v-label>

                <CustomArgumentsEditor
                  v-model:custom-args="packageStore.dictDetailEdit.custom_prj_args" />
              </v-col>
            </v-row>
          </v-container>
        </v-container>

        <!-- The button area. -->
        <v-container
          v-if="packageStore.dictDetailEdit"
          fluid
          class="pa-1 ma-0 d-flex ga-2 flex-shrink-0"
          style="height: 45px">
          <v-btn
            variant="tonal"
            prepend-icon="mdi-close"
            :disabled="!boolDetailChanged"
            @click="refreshDetail()">
            Cancel
          </v-btn>
          <v-spacer />
          <v-btn
            variant="tonal"
            prepend-icon="mdi-delete-outline"
            @click="openDeleteDialog()">
            Delete
          </v-btn>

          <v-btn
            variant="tonal"
            prepend-icon="mdi-content-save-outline"
            :disabled="!boolDetailChanged"
            @click="savePackageSettings()">
            Save
          </v-btn>

          <v-btn
            variant="tonal"
            prepend-icon="mdi-play-outline"
            :disabled="boolDetailChanged"
            @click="runPackage()">
            Run
          </v-btn>
        </v-container>

        <PackageRunDialog
          v-if="boolShowRunDialog && packageStore.dictDetailEdit"
          :package-details="packageStore.dictDetailEdit"
          @close="boolShowRunDialog = false" />

        <PackageDeleteDialog @deleted="resetProjectSelection" />
      </v-container>
    </v-container>
  </v-container>
</template>

<script setup lang="ts">
import PackageDeleteDialog from "./PackageDeleteDialog.vue";
import PackageDetails from "./PackageDetails.vue";
import PackageRunSettings from "./PackageRunSettings.vue";
import CustomArgumentsEditor from "../RunSettings/CustomArgumentsEditor.vue";
import PackageRunDialog from "./PackageRunDialog.vue";

import { onBeforeMount, onBeforeUnmount, ref, watch } from "vue";
import { debounce } from "lodash";

import { invokeMain } from "../../IPC/ipc";
import { loggerRenderer } from "../../Logging/logger";
import { usePackageStore } from "../../Store/packageStore";

const packageStore = usePackageStore();
const boolShowRunDialog = ref(false);
const strProjectName = ref("");
const strProjectVersion = ref("");
const arrSelectedProjectName = ref<string[]>([]);
const arrSelectedProjectVersion = ref<string[]>([]);
const boolDetailChanged = ref(false);

onBeforeMount(async () => {
  packageStore.resetVersionAndDetail();
  await packageStore.loadProjectNames();
});

function resetProjectSelection(): void {
  strProjectName.value = "";
  strProjectVersion.value = "";
  arrSelectedProjectName.value = [];
  arrSelectedProjectVersion.value = [];
  boolDetailChanged.value = false;
}

async function installPackage(): Promise<void> {
  loggerRenderer.debug("--installPackage--");

  const result = await invokeMain("installPackage");
  if (result.status === "canceled") {
    return;
  }

  packageStore.arrProjectName = [];
  await packageStore.loadProjectNames();

  strProjectName.value = result.project_name;
  arrSelectedProjectName.value = [result.project_name];
  await packageStore.loadProjectVersions(result.project_name);

  strProjectVersion.value = result.project_version;
  arrSelectedProjectVersion.value = [result.project_version];

  await packageStore.loadPackageDetails(result.project_name, result.project_version);
}

const debouncedSetButtonDisabled = debounce(() => {
  // Changed name or version.
  if (!packageStore.dictDetailEdit) {
    boolDetailChanged.value = false;
    return;
  }

  const strDetailCacheNew = JSON.stringify(packageStore.dictDetailEdit);
  if (strDetailCacheNew === packageStore.strDetailCacheEdit) {
    boolDetailChanged.value = false;
  } else {
    boolDetailChanged.value = true;
  }
}, 300);

watch(
  () => packageStore.dictDetailEdit,
  () => {
    debouncedSetButtonDisabled();
  },
  { deep: true },
);

onBeforeUnmount(() => {
  debouncedSetButtonDisabled.cancel();
});

async function refreshDetail(): Promise<void> {
  packageStore.resetDetail();
  await packageStore.loadPackageDetails(strProjectName.value, strProjectVersion.value);
}

/* Click triggers */

async function clickNewProjectItem(arrName: string[]): Promise<void> {
  const strSelectedName = arrName[0];
  if (strSelectedName === undefined) {
    return;
  }

  strProjectName.value = strSelectedName;
  strProjectVersion.value = "";
  arrSelectedProjectVersion.value = [];
  await packageStore.loadProjectVersions(strSelectedName);
}

async function clickNewProjectVersionItem(arrVersion: string[]): Promise<void> {
  const strSelectedVersion = arrVersion[0];
  if (strSelectedVersion === undefined) {
    return;
  }

  strProjectVersion.value = strSelectedVersion;
  await packageStore.loadPackageDetails(strProjectName.value, strSelectedVersion);
}

async function savePackageSettings(): Promise<void> {
  loggerRenderer.debug("--savePackageSettings--");
  await packageStore.savePackageSettings();
  await refreshDetail();
}

async function openDeleteDialog(): Promise<void> {
  const currentDetail = packageStore.dictDetailEdit;
  if (currentDetail !== undefined) {
    loggerRenderer.info(
      `Open delete dialog for Package: ${currentDetail.id}-${currentDetail.project_name}-${currentDetail.project_version}`,
    );
    await packageStore.loadBoundSchedules();
    if (packageStore.dictDetailEdit === currentDetail) {
      packageStore.showDeleteDialog = true;
    }
  }
}

function runPackage(): void {
  loggerRenderer.debug("--runPackage--");
  if (packageStore.dictDetailEdit) {
    boolShowRunDialog.value = true;
  }
}
</script>

<style scoped></style>
