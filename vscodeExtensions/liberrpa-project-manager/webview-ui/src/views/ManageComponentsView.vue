<!-- FileName: ManageComponentsView.vue -->
<template>
  <v-card class="mx-auto" max-width="1180">
    <v-card-title class="d-flex align-center pa-5 pb-2">
      <span class="text-h5">Manage Components</span>
      <v-spacer></v-spacer>
      <v-btn
        class="mr-2"
        prepend-icon="mdi-package-down"
        variant="text"
        :disabled="projectManagerStore.busy || repositoryCatalog === null"
        @click="importWheels">
        Import Wheels
      </v-btn>
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
        v-for="(warningMessage, intIndex) in componentManagementStore.warningMessages"
        :key="`manage-warning-${String(intIndex)}`"
        type="warning"
        variant="tonal"
        class="mb-3">
        {{ warningMessage }}
      </v-alert>

      <v-alert
        v-if="repositoryCatalogError !== null"
        type="error"
        variant="tonal"
        class="mb-4">
        <div class="font-weight-medium mb-1">
          Component Repository catalog is unavailable
        </div>
        <div>{{ repositoryCatalogError.message }}</div>
        <div
          v-if="repositoryCatalogError.code === 'repository_rebuild_required'"
          class="mt-2">
          Run "LiberRPA: Rebuild Component Repository Index", then refresh this page.
        </div>
        <div v-else class="mt-2">
          Check componentRepositoryPath and the Repository folder, then refresh this page.
        </div>
        <v-btn class="mt-3" size="small" variant="text" @click="showLogs">
          Show Logs
        </v-btn>
      </v-alert>

      <v-card variant="outlined" class="mb-5">
        <v-card-title class="text-subtitle-1"> Current direct dependencies </v-card-title>
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
                <div class="text-caption text-medium-emphasis">
                  {{ row.componentId }}
                </div>
              </td>
              <td>{{ row.requirement }}</td>
              <td>{{ row.version }}</td>
            </tr>
          </tbody>
        </v-table>
      </v-card>

      <template v-if="componentManagementStore.dependencyPlan === null">
        <DependencyOperationCard
          v-if="repositoryCatalog !== null"
          :project-state="projectState"
          :repository-catalog="repositoryCatalog"
          :busy="projectManagerStore.busy"
          @preview="previewPlan" />
        <RepairComponentsCard
          :repair-state="projectState.repairState"
          :busy="projectManagerStore.busy"
          @repair="repair" />
      </template>

      <DependencyPlanCard
        v-else
        :plan="componentManagementStore.dependencyPlan"
        :warning-messages="componentManagementStore.dependencyPlanWarningMessages"
        :component-package-names="componentPackageNames"
        :busy="projectManagerStore.busy"
        @back="clearPlan"
        @apply="applyPlan" />
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
import { computed } from "vue";

import { postMessage } from "../Adapter/Extension/vscodeApi";
import { useComponentManagementStore } from "../Application/ComponentManagement/componentManagementStore";
import { useProjectManagerStore } from "../Application/projectManagerStore";
import DependencyOperationCard from "../components/DependencyOperationCard.vue";
import DependencyPlanCard from "../components/DependencyPlanCard.vue";
import RepairComponentsCard from "../components/RepairComponentsCard.vue";
import type { DictProtocolDependencyOperation } from "../Domain/ComponentManagement/componentManagementTypes";

interface DictDirectDependencyRow {
  componentId: string;
  packageName: string;
  requirement: string;
  version: string;
}

const projectManagerStore = useProjectManagerStore();
const componentManagementStore = useComponentManagementStore();

const projectState = computed(() => {
  if (componentManagementStore.projectDependencyState === null) {
    throw new Error("Manage Components Project state is unavailable.");
  }
  return componentManagementStore.projectDependencyState;
});

const repositoryCatalog = computed(() => componentManagementStore.repositoryCatalog);

const repositoryCatalogError = computed(
  () => componentManagementStore.repositoryCatalogError,
);

const projectTitle = computed(() => {
  const manifest = projectState.value.manifest;
  return "id" in manifest ? manifest.displayName : manifest.name;
});

const componentPackageNames = computed<Record<string, string>>(() => {
  const dictPackageName: Record<string, string> = {};

  for (const component of repositoryCatalog.value?.components ?? []) {
    dictPackageName[component.componentId] = component.packageName;
  }
  for (const [componentId, component] of Object.entries(
    projectState.value.componentsLock?.components ?? {},
  )) {
    dictPackageName[componentId] = component.packageName;
  }

  return dictPackageName;
});

const directDependencyRows = computed<DictDirectDependencyRow[]>(() =>
  Object.entries(projectState.value.manifest.componentDependencies)
    .map(([componentId, currentRequirement]) => {
      const lockedComponent = projectState.value.componentsLock?.components[componentId];
      return {
        componentId,
        packageName:
          lockedComponent?.packageName ??
          componentPackageNames.value[componentId] ??
          componentId,
        requirement: currentRequirement,
        version: lockedComponent?.version ?? "Not resolved",
      };
    })
    .sort((left, right) => left.packageName.localeCompare(right.packageName)),
);

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

function previewPlan(dependencyOperation: DictProtocolDependencyOperation): void {
  if (projectManagerStore.busy) {
    return;
  }

  componentManagementStore.clearDependencyPlan();
  postMessage({ command: "buildProjectDependencyPlan", dependencyOperation });
}

function applyPlan(): void {
  const plan = componentManagementStore.dependencyPlan;
  const dependencyOperation = componentManagementStore.dependencyOperation;
  if (projectManagerStore.busy || plan === null || dependencyOperation === null) {
    return;
  }

  postMessage({
    command: "applyProjectDependencyPlan",
    dependencyOperation,
    confirmedPlanSha256: plan.planSha256,
  });
}

function repair(): void {
  if (projectManagerStore.busy || projectState.value.repairState !== "available") {
    return;
  }

  postMessage({ command: "repairProjectComponents" });
}

function importWheels(): void {
  if (!projectManagerStore.busy && repositoryCatalog.value !== null) {
    postMessage({ command: "importComponentWheels" });
  }
}

function showLogs(): void {
  postMessage({ command: "showLogs" });
}

function refresh(): void {
  if (!projectManagerStore.busy) {
    postMessage({ command: "refreshManageComponents" });
  }
}

function clearPlan(): void {
  if (!projectManagerStore.busy) {
    componentManagementStore.clearDependencyPlan();
  }
}

function cancel(): void {
  if (!projectManagerStore.busy) {
    postMessage({ command: "cancel" });
  }
}
</script>
