<!-- FileName: Alert.vue -->
<template>
  <v-alert
    v-if="projectManagerStore.showAlert"
    :text="projectManagerStore.alertMessage"
    :type="projectManagerStore.alertType"
    variant="flat"
    closable
    @click:close="clearInformation">
  </v-alert>
</template>

<script setup lang="ts">
import { onUnmounted, watch } from "vue";

import { useProjectManagerStore } from "../store";

const projectManagerStore = useProjectManagerStore();

let timeoutId: ReturnType<typeof setTimeout> | undefined;

function clearInformation(): void {
  projectManagerStore.clearAlert();
}

watch(
  [() => projectManagerStore.showAlert, () => projectManagerStore.alertMessage],
  ([showAlert, _alertMessage]) => {
    if (timeoutId !== undefined) {
      clearTimeout(timeoutId);
      timeoutId = undefined;
    }

    if (showAlert) {
      timeoutId = setTimeout(() => {
        clearInformation();
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

<style scoped></style>
