<!-- FileName: PackageProjectView.vue -->
<template>
  <v-card class="mx-auto" max-width="1080">
    <v-card-title class="d-flex align-center px-5 pt-5">
      <v-icon class="me-2">mdi-package-variant-closed</v-icon>
      Package Flow Project
      <v-spacer></v-spacer>
      <v-btn
        v-tooltip:bottom="'Refresh'"
        aria-label="Refresh"
        icon="mdi-refresh"
        variant="text"
        :disabled="projectManagerStore.busy"
        @click="refresh"></v-btn>
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
            <v-chip
              size="small"
              :color="COMPONENT_STATE_DISPLAY[projectDependencyState.lockState].color">
              Lock: {{ COMPONENT_STATE_DISPLAY[projectDependencyState.lockState].label }}
            </v-chip>

            <v-chip
              size="small"
              :color="
                COMPONENT_STATE_DISPLAY[projectDependencyState.componentsState].color
              ">
              _Components:
              {{ COMPONENT_STATE_DISPLAY[projectDependencyState.componentsState].label }}
            </v-chip>

            <v-chip
              size="small"
              :color="
                COMPONENT_STATE_DISPLAY[projectDependencyState.environmentState].color
              ">
              Environment:
              {{ COMPONENT_STATE_DISPLAY[projectDependencyState.environmentState].label }}
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
          <v-text-field
            v-model="packageProjectStore.outputFolderPath"
            label="Output folder"
            variant="plain"
            density="comfortable"
            readonly
            hide-details>
            <template #append-inner>
              <v-btn
                prepend-icon="mdi-folder-search-outline"
                variant="tonal"
                size="small"
                :disabled="projectManagerStore.busy"
                @click="selectOutputFolder">
                Browse
              </v-btn>
            </template>
          </v-text-field>

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
                  :color="packageCreated ? 'success' : 'error'">
                  {{ packageCreated ? "Created" : "Already exists" }}
                </v-chip>
              </div>
            </v-col>
          </v-row>

          <v-text-field
            v-model="packageProjectStore.versionSummary"
            class="mt-4"
            label="Version summary"
            placeholder="Summarize the changes in this version"
            hint="Optional. Up to 500 characters on one line, without surrounding whitespace."
            persistent-hint
            variant="outlined"
            density="comfortable"
            :error-messages="
              versionSummaryError === undefined ? [] : [versionSummaryError]
            "></v-text-field>

          <v-divider class="my-3"></v-divider>

          <div class="text-subtitle-2 mb-1">Optional package contents</div>

          <div class="text-body-2 text-medium-emphasis mb-2">
            Executor does not require these development and source-control entries, so they
            are excluded by default. Include them only when the packaged Project will also
            be used for development, testing or source-control transfer.
          </div>

          <v-checkbox
            v-model="packageProjectStore.includeVscodeSettings"
            label="Include VS Code settings (.vscode)"
            density="comfortable"
            hide-details></v-checkbox>

          <v-checkbox
            v-model="packageProjectStore.includeProjectTests"
            label="Include test and verification files (_Test)"
            density="comfortable"
            hide-details></v-checkbox>

          <v-checkbox
            v-model="packageProjectStore.includeGitRepository"
            label="Include Git repository and history (.git)"
            density="comfortable"
            hide-details></v-checkbox>

          <v-alert
            v-if="packageProjectStore.includeGitRepository"
            type="warning"
            variant="tonal"
            class="mt-3">
            The .git entry may be large and may contain remote URLs, complete history and
            content that was deleted from the current Project.
          </v-alert>
        </v-card-text>
      </v-card>

      <v-card variant="outlined" class="mb-4">
        <v-card-title class="text-subtitle-1">Console publishing</v-card-title>

        <v-card-text>
          <v-switch
            v-model="packageProjectStore.publishToConsole"
            label="Publish to Console"
            color="primary"
            :disabled="projectManagerStore.busy || packageCreated"
            hide-details
            @update:model-value="refreshConsolePublishing"></v-switch>

          <template v-if="packageProjectStore.publishToConsole">
            <v-alert
              v-if="packageProjectStore.consolePublishingMessage"
              type="warning"
              variant="tonal"
              class="mb-3">
              {{ packageProjectStore.consolePublishingMessage }}
              Use the Console command to manage your account, then refresh this page.
            </v-alert>

            <v-select
              v-model="packageProjectStore.consoleDepartmentId"
              :items="packageProjectStore.consoleDepartments"
              item-title="path"
              item-value="id"
              label="Publishing department"
              variant="outlined"
              density="comfortable"
              :disabled="projectManagerStore.busy || packageCreated"
              hide-details></v-select>
          </template>

          <v-alert
            v-if="
              packageProjectStore.consolePublishResult.status !==
              ConsolePublishStatus.NotRequested
            "
            :type="
              packageProjectStore.consolePublishResult.status ===
              ConsolePublishStatus.Failed
                ? 'warning'
                : packageProjectStore.consolePublishResult.status ===
                    ConsolePublishStatus.Completed
                  ? 'success'
                  : 'info'
            "
            variant="tonal"
            class="mt-3">
            {{ packageProjectStore.consolePublishResult.message }}
            <v-btn
              v-if="
                packageProjectStore.consolePublishResult.status ===
                ConsolePublishStatus.Failed
              "
              prepend-icon="mdi-refresh"
              class="mt-2"
              variant="tonal"
              size="small"
              :disabled="projectManagerStore.busy"
              @click="retryConsolePublish">
              Retry upload
            </v-btn>
          </v-alert>
        </v-card-text>
      </v-card>

      <v-alert
        v-if="packageProjectStore.packageFileExists && !packageCreated"
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

              <div class="font-weight-bold">
                {{ packageProjectStore.packageResult.fileCount }}
              </div>
            </v-col>

            <v-col cols="6" sm="3">
              <div class="text-caption">Folders</div>

              <div class="font-weight-bold">
                {{ packageProjectStore.packageResult.folderCount }}
              </div>
            </v-col>

            <v-col cols="6" sm="3">
              <div class="text-caption">Uncompressed size</div>

              <div class="font-weight-bold">
                {{ formatBytes(packageProjectStore.packageResult.uncompressedSizeBytes) }}
              </div>
            </v-col>

            <v-col cols="6" sm="3">
              <div class="text-caption">Archive size</div>

              <div class="font-weight-bold">
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

    <v-card-actions class="pa-5">
      <v-btn
        prepend-icon="mdi-close"
        variant="tonal"
        :disabled="projectManagerStore.busy"
        @click="close">
        Close
      </v-btn>

      <v-spacer></v-spacer>
      <v-btn
        variant="tonal"
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
import { COMPONENT_STATE_DISPLAY } from "../Application/ComponentManagement/componentStateDisplay";
import { usePackageProjectStore } from "../Application/PackageProject/packageProjectStore";
import { useProjectManagerStore } from "../Application/projectManagerStore";
import { getVersionSummaryError } from "../Domain/Project/projectValidation";
import { ConsolePublishStatus } from "../Domain/Console/consoleTypes";

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

const packageCreated = computed(() => packageProjectStore.packageResult !== null);

const versionSummaryError = computed(() =>
  getVersionSummaryError(packageProjectStore.versionSummary),
);

const canPackage = computed(
  () =>
    !projectManagerStore.busy &&
    packageProjectStore.outputFolderPath.length > 0 &&
    packageProjectStore.packageFileName !== null &&
    !packageProjectStore.packageFileExists &&
    versionSummaryError.value === undefined &&
    packageProjectStore.blockingReasons.length === 0 &&
    (!packageProjectStore.publishToConsole ||
      packageProjectStore.consoleDepartments.some(
        (department) => department.id === packageProjectStore.consoleDepartmentId,
      )),
);

function formatBytes(value: number): string {
  if (value < 1024) {
    return `${String(value)} B`;
  }

  const ARR_UNIT = ["KiB", "MiB", "GiB", "TiB"];
  let floatValue = value / 1024;
  let intUnitIndex = 0;
  while (floatValue >= 1024 && intUnitIndex < ARR_UNIT.length - 1) {
    floatValue /= 1024;
    intUnitIndex += 1;
  }
  return `${floatValue.toFixed(floatValue >= 10 ? 1 : 2)} ${ARR_UNIT[intUnitIndex]}`;
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

function retryConsolePublish(): void {
  if (!projectManagerStore.busy) {
    postMessage({ command: "retryConsolePublish" });
  }
}

function refreshConsolePublishing(): void {
  if (!projectManagerStore.busy) {
    postMessage({
      command: "refreshConsolePublishing",
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

<style scoped></style>
