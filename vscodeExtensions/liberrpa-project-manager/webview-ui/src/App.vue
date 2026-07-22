<!-- FileName: App.vue -->
<template>
  <v-app class="pa-0 ma-0 fill-height" :theme="projectManagerStore.theme">
    <v-main class="pa-0 ma-0 fill-height overflow-y-auto">
      <Alert style="position: fixed; width: 100%; opacity: 0.9; z-index: 999" />

      <v-container class="pa-4 pa-sm-6" style="min-height: 100vh">
        <v-card v-if="projectManagerStore.loaded" class="mx-auto" max-width="980">
          <v-card-title class="text-h5 pa-5 pb-2"> Create a New Project </v-card-title>

          <v-card-subtitle class="px-5 pb-4">
            Review all settings before creating the Project.
          </v-card-subtitle>

          <v-divider></v-divider>

          <v-card-text class="pa-5">
            <v-row>
              <v-col cols="12">
                <div class="text-subtitle-1 font-weight-medium mb-2">Project type</div>
                <v-radio-group
                  :model-value="projectManagerStore.projectType"
                  inline
                  hide-details
                  :disabled="projectManagerStore.busy"
                  @update:model-value="handleProjectTypeChange">
                  <v-radio label="Flow Project" value="flow"></v-radio>
                  <v-radio label="Component Project" value="component"></v-radio>
                </v-radio-group>
              </v-col>

              <v-col cols="12" md="6">
                <v-select
                  :model-value="projectManagerStore.templateName"
                  :items="availableTemplates"
                  item-title="templateName"
                  item-value="templateName"
                  label="Template"
                  :disabled="projectManagerStore.busy"
                  @update:model-value="handleTemplateChange">
                </v-select>
              </v-col>

              <v-col cols="12" md="6">
                <v-text-field
                  v-model="projectManagerStore.version"
                  label="Version"
                  placeholder="1.0.0"
                  hint="Use a Python PEP 440 version. Most users should use MAJOR.MINOR.PATCH."
                  persistent-hint
                  :error-messages="toErrorMessages(versionError)"
                  :disabled="projectManagerStore.busy">
                </v-text-field>
              </v-col>

              <v-col cols="12">
                <v-text-field
                  :model-value="projectManagerStore.targetFolder"
                  label="Target folder"
                  readonly
                  :error-messages="toErrorMessages(targetFolderError)"
                  :disabled="projectManagerStore.busy">
                  <template #append-inner>
                    <v-btn
                      variant="text"
                      size="small"
                      :disabled="projectManagerStore.busy"
                      @click="selectTargetFolder">
                      Browse
                    </v-btn>
                  </template>
                </v-text-field>
              </v-col>

              <v-col cols="12" md="6">
                <v-text-field
                  v-model="projectManagerStore.projectFolderName"
                  label="Project folder name"
                  :error-messages="toErrorMessages(projectFolderNameError)"
                  :disabled="projectManagerStore.busy">
                </v-text-field>
              </v-col>

              <template v-if="projectManagerStore.projectType === 'component'">
                <v-col cols="12" md="6">
                  <v-text-field
                    v-model="projectManagerStore.packageName"
                    label="Component package name"
                    placeholder="ExcelTools"
                    hint="PascalCase; used as the top-level Python package name."
                    persistent-hint
                    :error-messages="toErrorMessages(packageNameError)"
                    :disabled="projectManagerStore.busy">
                  </v-text-field>
                </v-col>

                <v-col cols="12">
                  <v-text-field
                    v-model="projectManagerStore.displayName"
                    label="Component display name"
                    hint="A readable name shown in Project Manager and Snippets Tree; leading and trailing whitespace is not allowed."
                    persistent-hint
                    :error-messages="toErrorMessages(displayNameError)"
                    :disabled="projectManagerStore.busy">
                  </v-text-field>
                </v-col>
              </template>

              <v-col cols="12">
                <v-textarea
                  v-model="projectManagerStore.description"
                  label="Description"
                  rows="3"
                  auto-grow
                  :disabled="projectManagerStore.busy">
                </v-textarea>
              </v-col>
            </v-row>
          </v-card-text>

          <v-divider></v-divider>

          <v-card-actions class="pa-5 justify-end">
            <v-btn variant="text" :disabled="projectManagerStore.busy" @click="cancel">
              Cancel
            </v-btn>
            <v-btn
              color="primary"
              variant="flat"
              :loading="projectManagerStore.busy"
              :disabled="!canConfirm"
              @click="confirm">
              Confirm
            </v-btn>
          </v-card-actions>
        </v-card>

        <div v-else class="fill-height d-flex align-center justify-center">
          <v-progress-circular indeterminate></v-progress-circular>
        </div>
      </v-container>
    </v-main>
  </v-app>
</template>

<script setup lang="ts">
import { computed, onBeforeMount, onUnmounted, watch } from "vue";

import { postMessage } from "./vscodeApi";
import Alert from "./components/Alert.vue";
import { useProjectManagerStore } from "./store";
import {
  REGEX_COMPONENT_PACKAGE_NAME,
  getProjectFolderNameError,
  getVersionInputError,
  getComponentPackageNameError,
  getDisplayNameError,
} from "./projectValidation";
import type { DictCreateProjectInput } from "./extensionMessages.ts";
import { isMessage_ExtensionToWebview } from "./extensionMessages.ts";

const projectManagerStore = useProjectManagerStore();

const availableTemplates = computed(() =>
  projectManagerStore.templates.filter(
    (item) => item.projectType === projectManagerStore.projectType,
  ),
);

const targetFolderError = computed(() =>
  projectManagerStore.targetFolder.length === 0 ? "Select a target folder." : undefined,
);

const projectFolderNameError = computed(() =>
  getProjectFolderNameError(projectManagerStore.projectFolderName),
);

const versionError = computed(() => getVersionInputError(projectManagerStore.version));

const packageNameError = computed(() =>
  projectManagerStore.projectType === "component"
    ? getComponentPackageNameError(projectManagerStore.packageName)
    : undefined,
);

const displayNameError = computed(() =>
  projectManagerStore.projectType === "component"
    ? getDisplayNameError(projectManagerStore.displayName)
    : undefined,
);

const canConfirm = computed(
  () =>
    projectManagerStore.loaded &&
    !projectManagerStore.busy &&
    projectManagerStore.templateName.length > 0 &&
    targetFolderError.value === undefined &&
    projectFolderNameError.value === undefined &&
    versionError.value === undefined &&
    packageNameError.value === undefined &&
    displayNameError.value === undefined,
);

let strLastSuggestedPackageName = "";
let strLastSuggestedDisplayName = "";

// Automatically suggest packageName and displayName.
watch(
  () => projectManagerStore.projectFolderName,
  (projectFolderName) => {
    if (projectManagerStore.projectType !== "component") {
      return;
    }

    if (
      projectManagerStore.packageName.length === 0 ||
      projectManagerStore.packageName === strLastSuggestedPackageName
    ) {
      const packageName = REGEX_COMPONENT_PACKAGE_NAME.test(projectFolderName)
        ? projectFolderName
        : "";
      projectManagerStore.packageName = packageName;
      strLastSuggestedPackageName = packageName;
    }

    if (
      projectManagerStore.displayName.length === 0 ||
      projectManagerStore.displayName === strLastSuggestedDisplayName
    ) {
      projectManagerStore.displayName = projectFolderName;
      strLastSuggestedDisplayName = projectFolderName;
    }
  },
);

function handleProjectTypeChange(value: unknown): void {
  if (value === "flow" || value === "component") {
    projectManagerStore.selectProjectType(value);

    if (value === "component") {
      updateComponentSuggestions();
    }
  }
}

function handleTemplateChange(value: unknown): void {
  if (typeof value === "string") {
    projectManagerStore.selectTemplate(value);
  }
}

function updateComponentSuggestions(): void {
  const projectFolderName = projectManagerStore.projectFolderName;

  if (projectManagerStore.packageName.length === 0) {
    const packageName = REGEX_COMPONENT_PACKAGE_NAME.test(projectFolderName)
      ? projectFolderName
      : "";
    projectManagerStore.packageName = packageName;
    strLastSuggestedPackageName = packageName;
  }

  if (projectManagerStore.displayName.length === 0) {
    projectManagerStore.displayName = projectFolderName;
    strLastSuggestedDisplayName = projectFolderName;
  }
}

function selectTargetFolder(): void {
  if (projectManagerStore.busy) {
    return;
  }

  postMessage({ command: "selectTargetFolder" });
}

function confirm(): void {
  if (!canConfirm.value) {
    return;
  }

  const dictInput: DictCreateProjectInput = {
    templateName: projectManagerStore.templateName,
    projectType: projectManagerStore.projectType,
    targetFolder: projectManagerStore.targetFolder,
    projectFolderName: projectManagerStore.projectFolderName,
    version: projectManagerStore.version,
    description: projectManagerStore.description,
    packageName: projectManagerStore.packageName,
    displayName: projectManagerStore.displayName,
  };

  // Disable all actions immediately instead of waiting for the Extension response.
  projectManagerStore.busy = true;
  postMessage({ command: "confirmCreateProject", input: dictInput });
}

function cancel(): void {
  if (projectManagerStore.busy) {
    return;
  }

  postMessage({ command: "cancel" });
}

function handleMessage(event: MessageEvent): void {
  const message: unknown = event.data;
  if (!isMessage_ExtensionToWebview(message)) {
    console.warn("Ignored invalid extension message:", message);
    return;
  }

  switch (message.command) {
    case "loadCreateProject":
      projectManagerStore.loadCreateProject(message.initialData);
      break;

    case "targetFolderSelected":
      projectManagerStore.targetFolder = message.path;
      break;

    case "setBusy":
      projectManagerStore.busy = message.busy;
      break;

    case "error":
      projectManagerStore.showMessage("error", message.message);
      break;

    case "themeChanged":
      projectManagerStore.theme = message.theme;
      break;
  }
}

function toErrorMessages(message: string | undefined): string[] {
  return message === undefined ? [] : [message];
}

onBeforeMount(() => {
  window.addEventListener("message", handleMessage);
  postMessage({ command: "ready" });
});

onUnmounted(() => {
  window.removeEventListener("message", handleMessage);
});
</script>

<style scoped></style>
