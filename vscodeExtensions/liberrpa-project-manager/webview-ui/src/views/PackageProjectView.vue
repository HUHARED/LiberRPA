<!-- FileName: PackageProjectView.vue -->
<template>
  <v-card class="mx-auto" max-width="1080" elevation="5">
    <v-card-title class="d-flex align-center px-5 pt-5">
      <v-icon class="me-2">mdi-package-variant-closed</v-icon>
      Package Flow Project
      <v-spacer></v-spacer>
      <v-btn
        icon="mdi-refresh"
        variant="text"
        :disabled="projectManagerStore.busy"
        @click="refresh">
      </v-btn>
    </v-card-title>

    <v-card-subtitle class="px-5 pb-2">
      Create an Executor Package from the current Flow Project.
    </v-card-subtitle>

    <v-card-text class="px-5 pb-5">
      <v-card variant="outlined" class="mb-4">
        <v-card-title class="text-subtitle-1 d-flex align-center">
          Project
          <v-spacer></v-spacer>
          <v-btn
            size="small"
            variant="tonal"
            prepend-icon="mdi-file-code-outline"
            :disabled="projectManagerStore.busy"
            @click="openManifest">
            Open flow.json
          </v-btn>
        </v-card-title>
        <v-card-text>
          <v-row>
            <v-col cols="12" md="6">
              <div class="text-caption text-medium-emphasis">Name</div>
              <div class="text-body-1">{{ manifest.name }}</div>
            </v-col>
            <v-col cols="12" md="3">
              <div class="text-caption text-medium-emphasis">Version</div>
              <div class="text-body-1">{{ manifest.version }}</div>
            </v-col>
            <v-col cols="12" md="3">
              <div class="text-caption text-medium-emphasis">Direct dependencies</div>
              <div class="text-body-1">{{ directDependencyCount }}</div>
            </v-col>
          </v-row>
          <v-row>
            <v-col cols="12">
              <div class="text-caption text-medium-emphasis">Description</div>
              <div class="text-body-2 text-pre-wrap">
                {{ manifest.description || "No description" }}
              </div>
            </v-col>
          </v-row>
          <v-row>
            <v-col cols="12">
              <div class="text-caption text-medium-emphasis">Project path</div>
              <div class="text-body-2 text-break">
                {{ packageProjectStore.projectPath }}
              </div>
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>

      <v-card variant="outlined" class="mb-4">
        <v-card-title class="text-subtitle-1 d-flex align-center">
          Component dependency state
          <v-spacer></v-spacer>
          <v-btn
            size="small"
            variant="tonal"
            prepend-icon="mdi-puzzle-outline"
            :disabled="projectManagerStore.busy"
            @click="openManageComponents">
            Manage Components
          </v-btn>
        </v-card-title>
        <v-card-text>
          <div class="d-flex flex-wrap ga-2 mb-3">
            <v-chip size="small" :color="getStateColor(projectDependencyState.lockState)">
              Lock: {{ projectDependencyState.lockState }}
            </v-chip>
            <v-chip
              size="small"
              :color="getStateColor(projectDependencyState.componentsState)">
              _Components: {{ projectDependencyState.componentsState }}
            </v-chip>
            <v-chip
              size="small"
              :color="getStateColor(projectDependencyState.environmentState)">
              Environment: {{ projectDependencyState.environmentState }}
            </v-chip>
          </div>
          <div class="text-body-2">Resolved Components: {{ resolvedComponentCount }}</div>
        </v-card-text>
      </v-card>

      <v-alert
        v-for="(reason, intIndex) in packageProjectStore.blockingReasons"
        :key="`package-blocking-${String(intIndex)}`"
        type="error"
        variant="tonal"
        class="mb-3">
        {{ reason }}
      </v-alert>

      <v-card variant="outlined" class="mb-4">
        <v-card-title class="text-subtitle-1">Package output</v-card-title>
        <v-card-text>
          <v-row align="center">
            <v-col cols="12" md="9">
              <v-text-field
                v-model="packageProjectStore.outputFolderPath"
                label="Output folder"
                variant="outlined"
                density="comfortable"
                readonly
                hide-details>
              </v-text-field>
            </v-col>
            <v-col cols="12" md="3">
              <v-btn
                block
                variant="tonal"
                prepend-icon="mdi-folder-open-outline"
                :disabled="projectManagerStore.busy"
                @click="selectOutputFolder">
                Select Folder
              </v-btn>
            </v-col>
          </v-row>

          <v-row>
            <v-col cols="12">
              <div class="text-caption text-medium-emphasis">Package filename</div>
              <div class="d-flex align-center flex-wrap ga-2">
                <span class="text-body-2 text-break">
                  {{ packageProjectStore.packageFileName ?? "Unavailable" }}
                </span>
                <v-chip
                  v-if="packageProjectStore.packageFileExists"
                  size="small"
                  color="error">
                  Already exists
                </v-chip>
              </div>
            </v-col>
          </v-row>

          <v-divider class="my-3"></v-divider>

          <v-checkbox
            v-model="packageProjectStore.includeVscodeSettings"
            label="Include VS Code settings (.vscode)"
            density="comfortable"
            hide-details>
          </v-checkbox>
          <v-checkbox
            v-model="packageProjectStore.includeGitRepository"
            label="Include Git repository and history (.git)"
            density="comfortable"
            hide-details>
          </v-checkbox>

          <v-alert
            v-if="packageProjectStore.includeGitRepository"
            type="warning"
            variant="tonal"
            class="mt-3">
            The .git folder may be large and may contain remote URLs, complete history and
            content that was deleted from the current Project.
          </v-alert>
        </v-card-text>
      </v-card>

      <v-alert
        v-if="packageProjectStore.packageFileExists"
        type="error"
        variant="tonal"
        class="mb-4">
        The target Package already exists. Existing .rpa.zip files are never overwritten.
        Change flow.json name/version or select another output folder.
      </v-alert>

      <v-card
        v-if="packageProjectStore.packageResult !== null"
        variant="outlined"
        class="mb-4">
        <v-card-title class="text-subtitle-1 d-flex align-center">
          Package result
          <v-spacer></v-spacer>
          <v-btn
            size="small"
            variant="tonal"
            prepend-icon="mdi-folder-search-outline"
            :disabled="projectManagerStore.busy"
            @click="revealPackage">
            Reveal
          </v-btn>
        </v-card-title>
        <v-card-text>
          <div class="text-caption text-medium-emphasis">Package file</div>
          <div class="text-body-2 text-break mb-3">
            {{ packageProjectStore.packageResult.packageFilePath }}
          </div>
          <v-row>
            <v-col cols="6" sm="3">
              <div class="text-caption">Files</div>
              <div class="font-weight-medium">
                {{ packageProjectStore.packageResult.fileCount }}
              </div>
            </v-col>
            <v-col cols="6" sm="3">
              <div class="text-caption">Folders</div>
              <div class="font-weight-medium">
                {{ packageProjectStore.packageResult.folderCount }}
              </div>
            </v-col>
            <v-col cols="6" sm="3">
              <div class="text-caption">Source size</div>
              <div class="font-weight-medium">
                {{ formatBytes(packageProjectStore.packageResult.uncompressedSizeBytes) }}
              </div>
            </v-col>
            <v-col cols="6" sm="3">
              <div class="text-caption">Archive size</div>
              <div class="font-weight-medium">
                {{ formatBytes(packageProjectStore.packageResult.packageSizeBytes) }}
              </div>
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>

      <v-alert
        v-for="(warningMessage, intIndex) in packageProjectStore.warningMessages"
        :key="`package-warning-${String(intIndex)}`"
        type="warning"
        variant="tonal"
        class="mb-3">
        {{ warningMessage }}
      </v-alert>
    </v-card-text>

    <v-divider></v-divider>

    <v-card-actions class="pa-5 justify-end">
      <v-btn variant="text" :disabled="projectManagerStore.busy" @click="close">
        Close
      </v-btn>
      <v-btn
        color="primary"
        prepend-icon="mdi-package-variant-closed-plus"
        :loading="projectManagerStore.busy"
        :disabled="!canPackage"
        @click="packageProject">
        Package Project
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from "vue";

import { postMessage } from "../Adapter/Extension/vscodeApi";
import { usePackageProjectStore } from "../Application/PackageProject/packageProjectStore";
import { useProjectManagerStore } from "../Application/projectManagerStore";

const projectManagerStore = useProjectManagerStore();
const packageProjectStore = usePackageProjectStore();

const manifest = computed(() => {
  if (packageProjectStore.manifest === null) {
    throw new Error("Package Project Manifest is unavailable.");
  }
  return packageProjectStore.manifest;
});

const projectDependencyState = computed(() => {
  if (packageProjectStore.projectDependencyState === null) {
    throw new Error("Package Project dependency state is unavailable.");
  }
  return packageProjectStore.projectDependencyState;
});

const directDependencyCount = computed(
  () => Object.keys(manifest.value.componentDependencies).length,
);
const resolvedComponentCount = computed(
  () => Object.keys(projectDependencyState.value.componentsLock?.components ?? {}).length,
);
const canPackage = computed(
  () =>
    !projectManagerStore.busy &&
    packageProjectStore.outputFolderPath.length > 0 &&
    packageProjectStore.packageFileName !== null &&
    !packageProjectStore.packageFileExists &&
    packageProjectStore.blockingReasons.length === 0,
);

function getStateColor(state: string): string | undefined {
  if (state === "valid" || state === "compatible" || state === "notRequired") {
    return "success";
  }
  if (state === "unknown" || state === "unverified") {
    return "warning";
  }
  return "error";
}

function formatBytes(value: number): string {
  if (value < 1024) {
    return `${String(value)} B`;
  }

  const arrUnit = ["KB", "MB", "GB", "TB"];
  let floatValue = value / 1024;
  let intUnitIndex = 0;
  while (floatValue >= 1024 && intUnitIndex < arrUnit.length - 1) {
    floatValue /= 1024;
    intUnitIndex += 1;
  }
  return `${floatValue.toFixed(floatValue >= 10 ? 1 : 2)} ${arrUnit[intUnitIndex]}`;
}

function selectOutputFolder(): void {
  if (!projectManagerStore.busy) {
    postMessage({
      command: "selectPackageOutputFolder",
      input: packageProjectStore.getInput(),
    });
  }
}

function packageProject(): void {
  if (canPackage.value) {
    postMessage({
      command: "runPackageProject",
      input: packageProjectStore.getInput(),
    });
  }
}

function refresh(): void {
  if (!projectManagerStore.busy) {
    postMessage({
      command: "refreshPackageProject",
      input: packageProjectStore.getInput(),
    });
  }
}

function openManifest(): void {
  if (!projectManagerStore.busy) {
    postMessage({ command: "openPackageProjectManifest" });
  }
}

function openManageComponents(): void {
  if (!projectManagerStore.busy) {
    postMessage({ command: "openManageComponents" });
  }
}

function revealPackage(): void {
  if (!projectManagerStore.busy) {
    postMessage({ command: "revealProjectPackage" });
  }
}

function close(): void {
  if (!projectManagerStore.busy) {
    postMessage({ command: "cancel" });
  }
}
</script>
