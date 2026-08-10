<!-- FileName: CreateProjectView.vue -->
<template>
  <v-card class="mx-auto" max-width="980">
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
            :model-value="createProjectStore.projectType"
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
            :model-value="createProjectStore.templateName"
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
            v-model="createProjectStore.version"
            label="Version"
            placeholder="1.0.0"
            hint="Use a Python PEP 440 version. Most users should use MAJOR.MINOR.PATCH."
            persistent-hint
            :error-messages="versionError"
            :disabled="projectManagerStore.busy">
          </v-text-field>
        </v-col>

        <v-col cols="12">
          <v-text-field
            :model-value="createProjectStore.targetFolderPath"
            label="Target folder"
            readonly
            :error-messages="targetFolderError"
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
            v-model="createProjectStore.projectFolderName"
            label="Project folder name"
            :error-messages="projectFolderNameError"
            :disabled="projectManagerStore.busy">
          </v-text-field>
        </v-col>

        <template v-if="createProjectStore.projectType === 'component'">
          <v-col cols="12" md="6">
            <v-text-field
              v-model="createProjectStore.packageName"
              label="Component package name"
              placeholder="ExcelTools"
              hint="PascalCase; used as the top-level Python package name."
              persistent-hint
              :error-messages="packageNameError"
              :disabled="projectManagerStore.busy">
            </v-text-field>
          </v-col>

          <v-col cols="12">
            <v-text-field
              v-model="createProjectStore.displayName"
              label="Component display name"
              :hint="STR_COMPONENT_DISPLAY_NAME_HINT"
              persistent-hint
              :error-messages="displayNameError"
              :disabled="projectManagerStore.busy">
            </v-text-field>
          </v-col>
        </template>

        <v-col cols="12">
          <v-textarea
            v-model="createProjectStore.description"
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
</template>

<script setup lang="ts">
import { computed, watch } from "vue";

import type { DictCreateProjectInput } from "../Domain/Project/projectTypes";
import { postMessage } from "../Adapter/Extension/vscodeApi";
import { useCreateProjectStore } from "../Application/CreateProject/createProjectStore";
import { useProjectManagerStore } from "../Application/projectManagerStore";
import {
  REGEX_COMPONENT_PACKAGE_NAME,
  getProjectFolderNameError,
  getVersionInputError,
  getComponentPackageNameError,
  getDisplayNameError,
} from "../Domain/Project/projectValidation";

const STR_COMPONENT_DISPLAY_NAME_HINT =
  "A readable name shown in Project Manager and Snippets Tree. " +
  "Leading and trailing whitespace is not allowed.";

const projectManagerStore = useProjectManagerStore();
const createProjectStore = useCreateProjectStore();

const availableTemplates = computed(() =>
  createProjectStore.templates.filter(
    (item) => item.projectType === createProjectStore.projectType,
  ),
);

const targetFolderError = computed(() =>
  createProjectStore.targetFolderPath.length === 0 ? "Select a target folder." : undefined,
);

const projectFolderNameError = computed(() =>
  getProjectFolderNameError(createProjectStore.projectFolderName),
);

const versionError = computed(() => getVersionInputError(createProjectStore.version));

const packageNameError = computed(() =>
  createProjectStore.projectType === "component"
    ? getComponentPackageNameError(createProjectStore.packageName)
    : undefined,
);

const displayNameError = computed(() =>
  createProjectStore.projectType === "component"
    ? getDisplayNameError(createProjectStore.displayName)
    : undefined,
);

const canConfirm = computed(
  () =>
    projectManagerStore.loaded &&
    !projectManagerStore.busy &&
    createProjectStore.templateName.length > 0 &&
    targetFolderError.value === undefined &&
    projectFolderNameError.value === undefined &&
    versionError.value === undefined &&
    packageNameError.value === undefined &&
    displayNameError.value === undefined,
);

let strLastSuggestedPackageName = "";
let strLastSuggestedDisplayName = "";

watch(
  () => createProjectStore.projectFolderName,
  (projectFolderName) => {
    if (createProjectStore.projectType !== "component") {
      return;
    }

    if (
      createProjectStore.packageName.length === 0 ||
      createProjectStore.packageName === strLastSuggestedPackageName
    ) {
      const packageName = REGEX_COMPONENT_PACKAGE_NAME.test(projectFolderName)
        ? projectFolderName
        : "";
      createProjectStore.packageName = packageName;
      strLastSuggestedPackageName = packageName;
    }

    if (
      createProjectStore.displayName.length === 0 ||
      createProjectStore.displayName === strLastSuggestedDisplayName
    ) {
      createProjectStore.displayName = projectFolderName;
      strLastSuggestedDisplayName = projectFolderName;
    }
  },
);

function handleProjectTypeChange(value: unknown): void {
  if (value === "flow" || value === "component") {
    createProjectStore.selectProjectType(value);

    if (value === "component") {
      updateComponentSuggestions();
    }
  }
}

function handleTemplateChange(value: unknown): void {
  if (typeof value === "string") {
    createProjectStore.selectTemplate(value);
  }
}

function updateComponentSuggestions(): void {
  const strProjectFolderName = createProjectStore.projectFolderName;

  if (createProjectStore.packageName.length === 0) {
    const packageName = REGEX_COMPONENT_PACKAGE_NAME.test(strProjectFolderName)
      ? strProjectFolderName
      : "";
    createProjectStore.packageName = packageName;
    strLastSuggestedPackageName = packageName;
  }

  if (createProjectStore.displayName.length === 0) {
    createProjectStore.displayName = strProjectFolderName;
    strLastSuggestedDisplayName = strProjectFolderName;
  }
}

function selectTargetFolder(): void {
  if (!projectManagerStore.busy) {
    postMessage({ command: "selectTargetFolder" });
  }
}

function confirm(): void {
  if (!canConfirm.value) {
    return;
  }

  const dictInput: DictCreateProjectInput = {
    templateName: createProjectStore.templateName,
    projectType: createProjectStore.projectType,

    targetFolderPath: createProjectStore.targetFolderPath,
    projectFolderName: createProjectStore.projectFolderName,

    version: createProjectStore.version,
    description: createProjectStore.description,
    packageName: createProjectStore.packageName,
    displayName: createProjectStore.displayName,
  };

  postMessage({ command: "confirmCreateProject", input: dictInput });
}

function cancel(): void {
  if (!projectManagerStore.busy) {
    postMessage({ command: "cancel" });
  }
}
</script>
