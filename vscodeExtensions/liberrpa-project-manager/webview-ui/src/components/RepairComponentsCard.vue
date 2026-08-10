<!-- FileName: RepairComponentsCard.vue -->
<template>
  <v-card variant="outlined">
    <v-card-title class="text-subtitle-1">Repair / Restore</v-card-title>
    <v-card-text>{{ description }}</v-card-text>
    <v-card-actions class="px-4 pb-4 justify-end">
      <v-btn
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

import type { Str_ProjectDependency_RepairState } from "../Domain/ComponentManagement/componentManagementTypes";

const props = defineProps<{
  repairState: Str_ProjectDependency_RepairState;
  busy: boolean;
}>();

const emit = defineEmits<{
  repair: [];
}>();

const description = computed(() => {
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
