<!-- FileName: DependencyPlanCard.vue -->
<template>
  <v-card variant="outlined">
    <v-card-title class="text-subtitle-1">Confirm dependency plan</v-card-title>
    <v-card-subtitle>Plan SHA-256: {{ plan.planSha256 }}</v-card-subtitle>

    <v-divider class="mt-3"></v-divider>

    <v-card-text>
      <v-alert
        v-for="(warningMessage, intIndex) in warningMessages"
        :key="`plan-warning-${String(intIndex)}`"
        type="warning"
        variant="tonal"
        class="mb-3">
        {{ warningMessage }}
      </v-alert>

      <div class="text-subtitle-2 mb-2">Direct dependency changes</div>
      <div
        v-if="plan.directDependencyChanges.length === 0"
        class="text-medium-emphasis mb-4">
        No direct Manifest dependency changes.
      </div>
      <v-list v-else density="compact" class="mb-4">
        <v-list-item
          v-for="change in plan.directDependencyChanges"
          :key="`${change.componentId}-${change.change}`">
          <v-list-item-title>{{ getDirectChangeText(change) }}</v-list-item-title>
          <v-list-item-subtitle>{{ change.componentId }}</v-list-item-subtitle>
        </v-list-item>
      </v-list>

      <div class="text-subtitle-2 mb-2">Resolved Component changes</div>
      <div v-if="plan.resolvedComponentChanges.length === 0" class="text-medium-emphasis">
        No resolved Component version changes were found.
      </div>
      <v-list v-else density="compact">
        <v-list-item
          v-for="change in plan.resolvedComponentChanges"
          :key="`${change.componentId}-${change.change}`">
          <v-list-item-title>{{ getResolvedChangeText(change) }}</v-list-item-title>
          <v-list-item-subtitle>{{ change.componentId }}</v-list-item-subtitle>
        </v-list-item>
      </v-list>
    </v-card-text>

    <v-divider></v-divider>

    <v-card-actions class="pa-4 justify-end">
      <v-btn variant="text" :disabled="busy" @click="emit('back')">Back</v-btn>
      <v-btn
        color="primary"
        variant="flat"
        :loading="busy"
        :disabled="!canApply"
        @click="emit('apply')">
        Confirm changes
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from "vue";

import type {
  DictProjectDependency_DirectChange,
  DictProjectDependency_ResolvedChange,
  DictProtocolResult_ProjectDependencyPlan,
} from "../Domain/ComponentManagement/componentManagementTypes";

const props = defineProps<{
  plan: DictProtocolResult_ProjectDependencyPlan;
  warningMessages: string[];
  componentPackageNames: Record<string, string>;
  busy: boolean;
}>();

const emit = defineEmits<{
  back: [];
  apply: [];
}>();

const canApply = computed(
  () =>
    !props.busy &&
    (props.plan.directDependencyChanges.length > 0 ||
      props.plan.resolvedComponentChanges.length > 0),
);

function getComponentPackageName(componentId: string): string {
  return props.componentPackageNames[componentId] ?? componentId;
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
        `${change.previousRequirement ?? ""} to ` +
        `${change.targetRequirement ?? ""}`
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
