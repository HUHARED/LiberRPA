<!-- FileName: RepairComponentsCard.vue -->
<template>
  <v-card variant="outlined">
    <v-card-title class="text-subtitle-1">Repair / Resolve</v-card-title>
    <v-card-text>{{ description }}</v-card-text>
    <v-card-actions class="px-4 pb-4 justify-end">
      <v-btn
        v-if="canResolve"
        color="primary"
        variant="outlined"
        :loading="busy"
        :disabled="busy || repositoryUnavailable"
        @click="emit('resolve')">
        Resolve dependencies
      </v-btn>
      <v-btn
        v-else
        color="primary"
        variant="outlined"
        :loading="busy"
        :disabled="busy || repairState !== 'available'"
        @click="emit('repair')">
        Repair _Components
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from "vue";

import type {
  Str_ProjectDependency_LockState,
  Str_ProjectDependency_RepairState,
} from "../Domain/ComponentManagement/componentManagementTypes";

const props = defineProps<{
  hasDependencies: boolean;
  lockState: Str_ProjectDependency_LockState;
  repairState: Str_ProjectDependency_RepairState;
  repositoryUnavailable: boolean;
  busy: boolean;
}>();

const emit = defineEmits<{
  repair: [];
  resolve: [];
}>();

const canResolve = computed(
  () =>
    props.hasDependencies &&
    (props.lockState === "missing" ||
      props.lockState === "invalid" ||
      props.lockState === "stale"),
);

const description = computed(() => {
  if (!props.hasDependencies) {
    return "This Project has no Component dependencies to repair or resolve.";
  }

  if (canResolve.value) {
    const strRepositoryUnavailable = props.repositoryUnavailable
      ? " The Component Repository catalog is unavailable, so resolution cannot run."
      : "";

    switch (props.lockState) {
      case "missing":
        return (
          "components.lock.json is missing. Resolve the current Manifest requirements to create a new lock file and rebuild _Components." +
          strRepositoryUnavailable
        );
      case "invalid":
        return (
          "components.lock.json is invalid. Resolve the current Manifest requirements to replace it and rebuild _Components." +
          strRepositoryUnavailable
        );
      case "stale":
        return (
          "components.lock.json no longer matches the current Manifest. Resolve the requirements again before applying other dependency operations." +
          strRepositoryUnavailable
        );
    }
  }

  switch (props.repairState) {
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
</script>
