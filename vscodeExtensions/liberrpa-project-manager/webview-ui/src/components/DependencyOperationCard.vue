<!-- FileName: DependencyOperationCard.vue -->
<template>
  <v-card variant="outlined" class="mb-5">
    <v-card-title class="text-subtitle-1">Dependency operation</v-card-title>
    <v-tabs v-model="selectedAction" grow :disabled="busy">
      <v-tab value="add">Add</v-tab>
      <v-tab value="update">Update</v-tab>
      <v-tab value="changeRequirement">Change requirement</v-tab>
      <v-tab value="remove">Remove</v-tab>
    </v-tabs>

    <v-divider></v-divider>

    <v-card-text class="pt-5">
      <template v-if="selectedAction === 'add'">
        <v-alert
          v-if="addComponentItems.length === 0"
          type="info"
          variant="tonal"
          class="mb-4">
          No additional Components are available in the local Repository.
        </v-alert>
        <v-autocomplete
          v-model="selectedComponentId"
          :items="addComponentItems"
          item-title="title"
          item-value="value"
          label="Component"
          hint="Select a Component from the local Component Repository."
          persistent-hint
          clearable
          :disabled="busy">
        </v-autocomplete>
        <v-alert
          v-if="selectedComponentOnlyHasPrereleaseVersions"
          type="info"
          variant="tonal"
          class="mt-3 mb-1">
          This Component has only pre-release versions in the local Repository. Enter an
          explicit pre-release requirement, such as <code>==1.2.0rc1</code>.
        </v-alert>
        <v-text-field
          v-model="requirement"
          class="mt-3"
          label="Version requirement"
          placeholder=">=1.0.0,<2"
          hint="Use a Python PEP 440 version specifier. Pre-release versions must be requested explicitly."
          persistent-hint
          :disabled="busy">
        </v-text-field>
      </template>

      <template v-else-if="selectedAction === 'update'">
        <v-alert
          v-if="installedComponentItems.length === 0"
          type="info"
          variant="tonal"
          class="mb-4">
          This Project has no resolved Components to update.
        </v-alert>
        <v-select
          v-model="selectedUpdateComponentIds"
          :items="installedComponentItems"
          item-title="title"
          item-value="value"
          label="Components to update"
          multiple
          chips
          closable-chips
          hint="Versions are updated only within the current Manifest requirements."
          persistent-hint
          :disabled="busy">
        </v-select>
      </template>

      <template v-else-if="selectedAction === 'changeRequirement'">
        <v-alert
          v-if="directDependencyItems.length === 0"
          type="info"
          variant="tonal"
          class="mb-4">
          This Project has no direct dependency requirement to change.
        </v-alert>
        <v-select
          v-model="selectedComponentId"
          :items="directDependencyItems"
          item-title="title"
          item-value="value"
          label="Direct dependency"
          :disabled="busy">
        </v-select>
        <v-text-field
          v-model="requirement"
          class="mt-3"
          label="New version requirement"
          placeholder=">=1.0.0,<2"
          hint="Use a Python PEP 440 version specifier. Pre-release versions must be requested explicitly."
          persistent-hint
          :disabled="busy">
        </v-text-field>
      </template>

      <template v-else>
        <v-alert
          v-if="directDependencyItems.length === 0"
          type="info"
          variant="tonal"
          class="mb-4">
          This Project has no direct dependency to remove.
        </v-alert>
        <v-select
          v-model="selectedComponentId"
          :items="directDependencyItems"
          item-title="title"
          item-value="value"
          label="Direct dependency to remove"
          hint="Unreachable transitive dependencies will also be removed."
          persistent-hint
          :disabled="busy">
        </v-select>
      </template>
    </v-card-text>

    <v-card-actions class="px-4 pb-4 justify-end">
      <v-btn
        color="primary"
        variant="flat"
        :loading="busy"
        :disabled="!canPreviewPlan"
        @click="previewPlan">
        Preview changes
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { getSuggestedComponentRequirement } from "../Domain/ComponentManagement/componentRequirement";
import type {
  DictProtocolDependencyOperation,
  DictProtocolResult_RepositoryCatalog_Component,
  DictProtocolResult_RepositoryCatalog,
  DictProtocolResult_ProjectDependencyState,
} from "../Domain/ComponentManagement/componentManagementTypes";

type ManageDependencyAction = "add" | "update" | "changeRequirement" | "remove";

interface DictSelectItem {
  title: string;
  value: string;
}

const props = defineProps<{
  projectState: DictProtocolResult_ProjectDependencyState;
  repositoryCatalog: DictProtocolResult_RepositoryCatalog;
  busy: boolean;
}>();

const emit = defineEmits<{
  preview: [dependencyOperation: DictProtocolDependencyOperation];
}>();

const selectedAction = ref<ManageDependencyAction>("add");
const selectedComponentId = ref<string | null>(null);
const selectedUpdateComponentIds = ref<string[]>([]);
const requirement = ref("");

const selectedRepositoryComponent = computed(() =>
  selectedComponentId.value === null
    ? undefined
    : props.repositoryCatalog.components.find(
        (component) => component.componentId === selectedComponentId.value,
      ),
);

const selectedComponentOnlyHasPrereleaseVersions = computed(() => {
  if (selectedAction.value !== "add") {
    return false;
  }

  const arrVersion = selectedRepositoryComponent.value?.versions ?? [];
  return (
    arrVersion.length > 0 &&
    arrVersion.every((versionEntry) => isCanonicalPrereleaseVersion(versionEntry.version))
  );
});

const directDependencyIdSet = computed(
  () => new Set(Object.keys(props.projectState.manifest.componentDependencies)),
);

const addComponentItems = computed<DictSelectItem[]>(() =>
  props.repositoryCatalog.components
    .filter(
      (component) =>
        !directDependencyIdSet.value.has(component.componentId) &&
        (!("id" in props.projectState.manifest) ||
          component.componentId !== props.projectState.manifest.id),
    )
    .map((component) => ({
      title: getRepositoryComponentTitle(component),
      value: component.componentId,
    }))
    .sort((left, right) => left.title.localeCompare(right.title)),
);

const installedComponentItems = computed<DictSelectItem[]>(() => {
  const components = props.projectState.componentsLock?.components ?? {};
  return Object.entries(components)
    .map(([componentId, component]) => ({
      title: `${component.packageName} ${component.version}`,
      value: componentId,
    }))
    .sort((left, right) => left.title.localeCompare(right.title));
});

const directDependencyItems = computed<DictSelectItem[]>(() =>
  Object.entries(props.projectState.manifest.componentDependencies)
    .map(([componentId, currentRequirement]) => ({
      title: `${getComponentPackageName(componentId)} (${currentRequirement})`,
      value: componentId,
    }))
    .sort((left, right) => left.title.localeCompare(right.title)),
);

const canPreviewPlan = computed(() => {
  if (props.busy) {
    return false;
  }

  switch (selectedAction.value) {
    case "add":
      return selectedComponentId.value !== null && requirement.value.trim().length > 0;
    case "update":
      return selectedUpdateComponentIds.value.length > 0;
    case "changeRequirement":
      return (
        selectedComponentId.value !== null &&
        requirement.value.trim().length > 0 &&
        requirement.value.trim() !==
          props.projectState.manifest.componentDependencies[selectedComponentId.value]
      );
    case "remove":
      return selectedComponentId.value !== null;
  }
});

function resetInput(): void {
  selectedComponentId.value = null;
  selectedUpdateComponentIds.value = [];
  requirement.value = "";
}

watch(selectedAction, resetInput);
watch(() => props.projectState, resetInput);

watch(selectedComponentId, (componentId) => {
  if (componentId === null) {
    requirement.value = "";
    return;
  }

  if (selectedAction.value === "add") {
    const latestSimpleRelease = selectedRepositoryComponent.value?.versions.find((item) =>
      /^\d+(?:\.\d+){0,2}$/.test(item.version),
    )?.version;
    requirement.value =
      latestSimpleRelease === undefined
        ? ""
        : getSuggestedComponentRequirement(latestSimpleRelease);
  } else if (selectedAction.value === "changeRequirement") {
    requirement.value =
      props.projectState.manifest.componentDependencies[componentId] ?? "";
  }
});

function isCanonicalPrereleaseVersion(version: string): boolean {
  // Repository versions have already been normalized by Python packaging.
  return /(?:a|b|rc)\d+/.test(version) || /\.dev\d+/.test(version);
}

function getRepositoryComponentTitle(
  component: DictProtocolResult_RepositoryCatalog_Component,
): string {
  const latestVersion = component.versions[0];
  const displayName = latestVersion?.displayName ?? component.packageName;
  const version = latestVersion?.version ?? "No versions";
  return `${displayName} · ${component.packageName} · ${version}`;
}

function getComponentPackageName(componentId: string): string {
  return (
    props.projectState.componentsLock?.components[componentId]?.packageName ??
    props.repositoryCatalog.components.find((item) => item.componentId === componentId)
      ?.packageName ??
    componentId
  );
}

function buildDependencyOperation(): DictProtocolDependencyOperation | null {
  const componentId = selectedComponentId.value;
  switch (selectedAction.value) {
    case "add":
      return componentId === null
        ? null
        : {
            operation: "addComponentDependency",
            componentId,
            requirement: requirement.value.trim(),
          };
    case "update":
      return {
        operation: "updateComponents",
        componentIds: [...selectedUpdateComponentIds.value],
      };
    case "changeRequirement":
      return componentId === null
        ? null
        : {
            operation: "changeComponentRequirement",
            componentId,
            requirement: requirement.value.trim(),
          };
    case "remove":
      return componentId === null
        ? null
        : {
            operation: "removeComponentDependency",
            componentId,
          };
  }
}

function previewPlan(): void {
  if (!canPreviewPlan.value) {
    return;
  }

  const dependencyOperation = buildDependencyOperation();
  if (dependencyOperation !== null) {
    emit("preview", dependencyOperation);
  }
}
</script>
