<!-- FileName: Alert.vue -->
<template>
  <v-alert
    v-if="projectManagerStore.showAlert"
    :text="projectManagerStore.alertMessage"
    :type="projectManagerStore.alertType"
    variant="flat"
    closable
    @click:close="clearAlert">
  </v-alert>
</template>

<script setup lang="ts">
import { onUnmounted, watch } from "vue";

import { useProjectManagerStore } from "../Application/projectManagerStore";

const projectManagerStore = useProjectManagerStore();
let timeoutId: ReturnType<typeof setTimeout> | undefined;

function clearAlert(): void {
  projectManagerStore.clearAlert();
}

watch(
  [() => projectManagerStore.showAlert, () => projectManagerStore.alertMessage],
  ([boolShowAlert]) => {
    if (timeoutId !== undefined) {
      clearTimeout(timeoutId);
      timeoutId = undefined;
    }

    if (boolShowAlert) {
      timeoutId = setTimeout(() => {
        clearAlert();
        timeoutId = undefined;
      }, 5000);
    }
  },
);

onUnmounted(() => {
  if (timeoutId !== undefined) {
    clearTimeout(timeoutId);
  }
});
</script>
