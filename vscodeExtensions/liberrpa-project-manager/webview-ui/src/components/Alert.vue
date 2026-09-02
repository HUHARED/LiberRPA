<!-- FileName: Alert.vue -->
<template>
  <v-alert
    v-if="projectManagerStore.showAlert"
    :key="projectManagerStore.alertRevision"
    :type="projectManagerStore.alertType"
    variant="flat"
    closable
    @click:close="clearAlert">
    <div class="d-flex align-center ga-2">
      <span class="flex-grow-1">{{ projectManagerStore.alertMessage }}</span>
      <v-btn
        v-if="projectManagerStore.alertType === 'error'"
        variant="text"
        size="small"
        @click.stop="showLogs">
        Show Logs
      </v-btn>
    </div>
  </v-alert>
</template>

<script setup lang="ts">
import { onUnmounted, watch } from "vue";

import { postMessage } from "../Adapter/Extension/vscodeApi";
import { useProjectManagerStore } from "../Application/projectManagerStore";

const projectManagerStore = useProjectManagerStore();
let timeoutId: ReturnType<typeof setTimeout> | undefined;

function clearAlert(): void {
  projectManagerStore.clearAlert();
}

function showLogs(): void {
  postMessage({ command: "showLogs" });
}

watch(
  [
    () => projectManagerStore.showAlert,
    () => projectManagerStore.alertMessage,
    () => projectManagerStore.alertType,
    () => projectManagerStore.alertRevision,
  ],
  ([boolShowAlert, , alertType]) => {
    if (timeoutId !== undefined) {
      clearTimeout(timeoutId);
      timeoutId = undefined;
    }

    if (boolShowAlert && alertType !== "error") {
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
