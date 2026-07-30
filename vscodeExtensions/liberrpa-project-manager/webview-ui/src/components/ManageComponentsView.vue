<!-- FileName: ManageComponentsView.vue -->
<template>
  <v-card class="mx-auto" max-width="1180">
    <v-card-title class="d-flex align-center pa-5 pb-2">
      <span class="text-h5">Manage Components</span>
      <v-spacer></v-spacer>
      <v-btn
        icon="mdi-refresh"
        variant="text"
        :disabled="projectManagerStore.busy"
        @click="refresh">
      </v-btn>
    </v-card-title>

    <v-card-subtitle class="px-5 pb-4">
      {{ projectTitle }} · {{ projectState.projectPath }}
    </v-card-subtitle>

    <v-divider></v-divider>

    <v-card-text class="pa-5">
      <v-row class="mb-1">
        <v-col cols="12" sm="6" lg="3">
          <v-card variant="tonal" class="pa-3 h-100">
            <div class="text-caption mb-1">Lock</div>
            <v-chip size="small" :color="getStateColor(projectState.lockState)">
              {{ projectState.lockState }}
            </v-chip>
          </v-card>
        </v-col>
        <v-col cols="12" sm="6" lg="3">
          <v-card variant="tonal" class="pa-3 h-100">
            <div class="text-caption mb-1">_Components</div>
            <v-chip size="small" :color="getStateColor(projectState.componentsState)">
              {{ projectState.componentsState }}
            </v-chip>
          </v-card>
        </v-col>
        <v-col cols="12" sm="6" lg="3">
          <v-card variant="tonal" class="pa-3 h-100">
            <div class="text-caption mb-1">Environment</div>
            <v-chip size="small" :color="getStateColor(projectState.environmentState)">
              {{ projectState.environmentState }}
            </v-chip>
          </v-card>
        </v-col>
        <v-col cols="12" sm="6" lg="3">
          <v-card variant="tonal" class="pa-3 h-100">
            <div class="text-caption mb-1">Repair</div>
            <v-chip size="small" :color="getStateColor(projectState.repairState)">
              {{ projectState.repairState }}
            </v-chip>
          </v-card>
        </v-col>
      </v-row>

      <v-alert
        v-for="(warningMessage, intIndex) in projectManagerStore.manageWarningMessages"
        :key="`manage-warning-${String(intIndex)}`"
        type="warning"
        variant="tonal"
        class="mb-3">
        {{ warningMessage }}
      </v-alert>

      <v-card variant="outlined" class="mb-5">
        <v-card-title class="text-subtitle-1">Current direct dependencies</v-card-title>
        <v-card-text v-if="directDependencyRows.length === 0" class="text-medium-emphasis">
          This Project has no direct Component dependencies.
        </v-card-text>
        <v-table v-else density="compact">
          <thead>
            <tr>
              <th>Component</th>
              <th>Requirement</th>
              <th>Resolved version</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in directDependencyRows" :key="row.componentId">
              <td>
                <div class="font-weight-medium">{{ row.packageName }}</div>
                <div class="text-caption text-medium-emphasis">{{ row.componentId }}</div>
              </td>
              <td>{{ row.requirement }}</td>
              <td>{{ row.version }}</td>
            </tr>
          </tbody>
        </v-table>
      </v-card>

      <template v-if="projectManagerStore.dependencyPlan === null">
        <v-card variant="outlined" class="mb-5">
          <v-card-title class="text-subtitle-1">Dependency operation</v-card-title>
          <v-tabs v-model="selectedAction" grow :disabled="projectManagerStore.busy">
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
                :disabled="projectManagerStore.busy">
              </v-autocomplete>
              <v-text-field
                v-model="requirement"
                class="mt-3"
                label="Version requirement"
                placeholder=">=1.0.0,<2"
                hint="Use a Python PEP 440 version specifier."
                persistent-hint
                :disabled="projectManagerStore.busy">
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
                :disabled="projectManagerStore.busy">
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
                :disabled="projectManagerStore.busy">
              </v-select>
              <v-text-field
                v-model="requirement"
                class="mt-3"
                label="New version requirement"
                placeholder=">=1.0.0,<2"
                :disabled="projectManagerStore.busy">
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
                :disabled="projectManagerStore.busy">
              </v-select>
            </template>
          </v-card-text>

          <v-card-actions class="px-4 pb-4 justify-end">
            <v-btn
              color="primary"
              variant="flat"
              :loading="projectManagerStore.busy"
              :disabled="!canPreviewPlan"
              @click="previewPlan">
              Preview changes
            </v-btn>
          </v-card-actions>
        </v-card>

        <v-card variant="outlined">
          <v-card-title class="text-subtitle-1">Repair / Restore</v-card-title>
          <v-card-text>
            {{ repairDescription }}
          </v-card-text>
          <v-card-actions class="px-4 pb-4 justify-end">
            <v-btn
              color="primary"
              variant="outlined"
              :loading="projectManagerStore.busy"
              :disabled="projectState.repairState !== 'available'"
              @click="repair">
              Repair _Components
            </v-btn>
          </v-card-actions>
        </v-card>
      </template>

      <template v-else>
        <v-card variant="outlined">
          <v-card-title class="text-subtitle-1">Confirm dependency plan</v-card-title>
          <v-card-subtitle>
            Plan SHA-256: {{ projectManagerStore.dependencyPlan.planSha256 }}
          </v-card-subtitle>

          <v-divider class="mt-3"></v-divider>

          <v-card-text>
            <v-alert
              v-for="(
                warningMessage, intIndex
              ) in projectManagerStore.dependencyPlanWarningMessages"
              :key="`plan-warning-${String(intIndex)}`"
              type="warning"
              variant="tonal"
              class="mb-3">
              {{ warningMessage }}
            </v-alert>

            <div class="text-subtitle-2 mb-2">Direct dependency changes</div>
            <div
              v-if="projectManagerStore.dependencyPlan.directDependencyChanges.length === 0"
              class="text-medium-emphasis mb-4">
              No direct Manifest dependency changes.
            </div>
            <v-list v-else density="compact" class="mb-4">
              <v-list-item
                v-for="change in projectManagerStore.dependencyPlan.directDependencyChanges"
                :key="`${change.componentId}-${change.change}`">
                <v-list-item-title>
                  {{ getDirectChangeText(change) }}
                </v-list-item-title>
                <v-list-item-subtitle>{{ change.componentId }}</v-list-item-subtitle>
              </v-list-item>
            </v-list>

            <div class="text-subtitle-2 mb-2">Resolved Component changes</div>
            <div
              v-if="
                projectManagerStore.dependencyPlan.resolvedComponentChanges.length === 0
              "
              class="text-medium-emphasis">
              No resolved Component version changes were found.
            </div>
            <v-list v-else density="compact">
              <v-list-item
                v-for="change in projectManagerStore.dependencyPlan
                  .resolvedComponentChanges"
                :key="`${change.componentId}-${change.change}`">
                <v-list-item-title>
                  {{ getResolvedChangeText(change) }}
                </v-list-item-title>
                <v-list-item-subtitle>{{ change.componentId }}</v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </v-card-text>

          <v-divider></v-divider>

          <v-card-actions class="pa-4 justify-end">
            <v-btn variant="text" :disabled="projectManagerStore.busy" @click="clearPlan">
              Back
            </v-btn>
            <v-btn
              color="primary"
              variant="flat"
              :loading="projectManagerStore.busy"
              :disabled="!canApplyPlan"
              @click="applyPlan">
              Confirm changes
            </v-btn>
          </v-card-actions>
        </v-card>
      </template>
    </v-card-text>

    <v-divider></v-divider>

    <v-card-actions class="pa-5 justify-end">
      <v-btn variant="text" :disabled="projectManagerStore.busy" @click="cancel">
        Close
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";

import type {
  DictProtocolDependencyOperation,
  DictProtocolResult_RepositoryCatalog_Component,
  DictProjectDependency_DirectChange,
  DictProjectDependency_ResolvedChange,
} from "../componentManagement/protocol";
import { postMessage } from "../vscodeApi";
import { useProjectManagerStore } from "../store";

type ManageDependencyAction = "add" | "update" | "changeRequirement" | "remove";

interface DictSelectItem {
  title: string;
  value: string;
}

interface DictDirectDependencyRow {
  componentId: string;
  packageName: string;
  requirement: string;
  version: string;
}

const projectManagerStore = useProjectManagerStore();
const selectedAction = ref<ManageDependencyAction>("add");
const selectedComponentId = ref<string | null>(null);
const selectedUpdateComponentIds = ref<string[]>([]);
const requirement = ref("");

const projectState = computed(() => {
  if (projectManagerStore.projectDependencyState === null) {
    throw new Error("Manage Components Project state is unavailable.");
  }
  return projectManagerStore.projectDependencyState;
});

const repositoryCatalog = computed(() => {
  if (projectManagerStore.repositoryCatalog === null) {
    throw new Error("Manage Components Repository catalog is unavailable.");
  }
  return projectManagerStore.repositoryCatalog;
});

const projectTitle = computed(() => {
  const manifest = projectState.value.manifest;
  return "id" in manifest ? manifest.displayName : manifest.name;
});

const directDependencyIdSet = computed(
  () => new Set(Object.keys(projectState.value.manifest.componentDependencies)),
);

const addComponentItems = computed<DictSelectItem[]>(() =>
  repositoryCatalog.value.components
    .filter(
      (component) =>
        !directDependencyIdSet.value.has(component.componentId) &&
        (!("id" in projectState.value.manifest) ||
          component.componentId !== projectState.value.manifest.id),
    )
    .map((component) => ({
      title: getRepositoryComponentTitle(component),
      value: component.componentId,
    })),
);

const installedComponentItems = computed<DictSelectItem[]>(() => {
  const components = projectState.value.componentsLock?.components ?? {};
  return Object.entries(components)
    .map(([componentId, component]) => ({
      title: `${component.packageName} ${component.version}`,
      value: componentId,
    }))
    .sort((left, right) => left.title.localeCompare(right.title));
});

const directDependencyItems = computed<DictSelectItem[]>(() =>
  Object.entries(projectState.value.manifest.componentDependencies)
    .map(([componentId, currentRequirement]) => ({
      title: `${getComponentPackageName(componentId)} (${currentRequirement})`,
      value: componentId,
    }))
    .sort((left, right) => left.title.localeCompare(right.title)),
);

const directDependencyRows = computed<DictDirectDependencyRow[]>(() =>
  Object.entries(projectState.value.manifest.componentDependencies)
    .map(([componentId, currentRequirement]) => {
      const lockedComponent = projectState.value.componentsLock?.components[componentId];
      return {
        componentId,
        packageName: lockedComponent?.packageName ?? getComponentPackageName(componentId),
        requirement: currentRequirement,
        version: lockedComponent?.version ?? "Not resolved",
      };
    })
    .sort((left, right) => left.packageName.localeCompare(right.packageName)),
);

const canPreviewPlan = computed(() => {
  if (projectManagerStore.busy) {
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
          projectState.value.manifest.componentDependencies[selectedComponentId.value]
      );
    case "remove":
      return selectedComponentId.value !== null;
  }
});

const canApplyPlan = computed(() => {
  const plan = projectManagerStore.dependencyPlan;
  return (
    plan !== null &&
    !projectManagerStore.busy &&
    (plan.directDependencyChanges.length > 0 || plan.resolvedComponentChanges.length > 0)
  );
});

const repairDescription = computed(() => {
  switch (projectState.value.repairState) {
    case "available":
      return "The current _Components folder can be rebuilt from the exact Wheels recorded in components.lock.json.";
    case "repositoryUnavailable":
      return "The Component Repository is unavailable, so Repair cannot run.";
    case "wheelMissing":
      return "At least one exact Component Wheel required by the lock file is missing.";
    case "wheelHashMismatch":
      return "At least one Repository Wheel does not match the SHA-256 recorded in the lock file.";
    case "notApplicable":
      return "Repair is not required or the current lock state does not permit Repair.";
  }
});

function resetOperationInput(): void {
  selectedComponentId.value = null;
  selectedUpdateComponentIds.value = [];
  requirement.value = "";
  projectManagerStore.clearDependencyPlan();
}

watch(selectedAction, () => {
  resetOperationInput();
});

watch(
  () => projectManagerStore.projectDependencyState,
  () => {
    resetOperationInput();
  },
);

watch(selectedComponentId, (componentId) => {
  if (componentId === null) {
    requirement.value = "";
    return;
  }

  if (selectedAction.value === "add") {
    const component = repositoryCatalog.value.components.find(
      (item) => item.componentId === componentId,
    );
    const latestSimpleRelease = component?.versions.find((item) =>
      /^\d+(?:\.\d+){0,2}$/.test(item.version),
    )?.version;
    requirement.value =
      latestSimpleRelease === undefined ? "" : getSuggestedRequirement(latestSimpleRelease);
  } else if (selectedAction.value === "changeRequirement") {
    requirement.value =
      projectState.value.manifest.componentDependencies[componentId] ?? "";
  }
});

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
    projectState.value.componentsLock?.components[componentId]?.packageName ??
    repositoryCatalog.value.components.find((item) => item.componentId === componentId)
      ?.packageName ??
    componentId
  );
}

function getSuggestedRequirement(version: string): string {
  const match = /^(\d+)(?:\.(\d+))?(?:\.(\d+))?$/.exec(version);
  if (match === null) {
    return `==${version}`;
  }

  const intMajor = Number(match[1]);
  return `>=${version},<${String(intMajor + 1)}`;
}

function getStateColor(state: string): string | undefined {
  if (state === "valid" || state === "compatible" || state === "notRequired") {
    return "success";
  }
  if (state === "available" || state === "unknown" || state === "unverified") {
    return "warning";
  }
  if (state === "notApplicable") {
    return undefined;
  }
  return "error";
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
  if (dependencyOperation === null) {
    return;
  }

  projectManagerStore.busy = true;
  projectManagerStore.clearDependencyPlan();
  postMessage({ command: "buildProjectDependencyPlan", dependencyOperation });
}

function applyPlan(): void {
  if (
    !canApplyPlan.value ||
    projectManagerStore.dependencyPlan === null ||
    projectManagerStore.dependencyOperation === null
  ) {
    return;
  }

  projectManagerStore.busy = true;
  postMessage({
    command: "applyProjectDependencyPlan",
    dependencyOperation: projectManagerStore.dependencyOperation,
    confirmedPlanSha256: projectManagerStore.dependencyPlan.planSha256,
  });
}

function repair(): void {
  if (projectState.value.repairState !== "available" || projectManagerStore.busy) {
    return;
  }

  projectManagerStore.busy = true;
  postMessage({ command: "repairProjectComponents" });
}

function refresh(): void {
  if (!projectManagerStore.busy) {
    projectManagerStore.busy = true;
    postMessage({ command: "refreshManageComponents" });
  }
}

function clearPlan(): void {
  if (!projectManagerStore.busy) {
    projectManagerStore.clearDependencyPlan();
  }
}

function cancel(): void {
  if (!projectManagerStore.busy) {
    postMessage({ command: "cancel" });
  }
}

function getDirectChangeText(change: DictProjectDependency_DirectChange): string {
  switch (change.change) {
    case "added":
      return `Add ${getComponentPackageName(change.componentId)} with requirement ${change.targetRequirement ?? ""}`;
    case "removed":
      return `Remove ${getComponentPackageName(change.componentId)} from direct dependencies`;
    case "requirementChanged":
      return (
        `Change ${getComponentPackageName(change.componentId)} requirement from ` +
        `${change.previousRequirement ?? ""} to ${change.targetRequirement ?? ""}`
      );
  }
}

function getResolvedChangeText(change: DictProjectDependency_ResolvedChange): string {
  switch (change.change) {
    case "added":
      return `Add ${change.packageName} ${change.targetVersion ?? ""}`;
    case "removed":
      return `Remove ${change.packageName} ${change.previousVersion ?? ""}`;
    case "upgraded":
      return `Upgrade ${change.packageName} from ${change.previousVersion ?? ""} to ${change.targetVersion ?? ""}`;
    case "downgraded":
      return `Downgrade ${change.packageName} from ${change.previousVersion ?? ""} to ${change.targetVersion ?? ""}`;
  }
}
</script>
