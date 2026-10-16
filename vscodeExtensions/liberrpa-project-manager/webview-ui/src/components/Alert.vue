<!-- FileName: Alert.vue -->
<template>
  <v-alert
    v-if="projectManagerStore.showAlert"
    :key="projectManagerStore.alertRevision"
    :type="projectManagerStore.alertType"
    :text="projectManagerStore.alertMessage"
    variant="flat"
    closable
    @click:close="clearAlert">
    <template v-if="projectManagerStore.alertType === 'error'" #append>
      <v-btn
        prepend-icon="mdi-text-box-outline"
        variant="tonal"
        size="small"
        @click.stop="showLogs">
        Show Logs
      </v-btn>
    </template>
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

<style scoped></style>
