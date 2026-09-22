<!-- FileName: Alert.vue -->
<template>
  <v-alert
    v-if="informationStore.showAlert"
    style="position: fixed; width: 100%; opacity: 0.9; z-index: 999"
    variant="flat"
    type="warning"
    closable
    @click:close="closeAlert">
    <div class="alert-message">{{ informationStore.strAlertMessage }}</div>
  </v-alert>
</template>

<script setup lang="ts">
import { onBeforeUnmount, watch } from "vue";

import { useInformationStore } from "../store";

const informationStore = useInformationStore();
let timeoutCloseAlert: ReturnType<typeof setTimeout> | undefined;

function clearCloseAlertTimer(): void {
  if (timeoutCloseAlert !== undefined) {
    clearTimeout(timeoutCloseAlert);
    timeoutCloseAlert = undefined;
  }
}

function closeAlert(): void {
  clearCloseAlertTimer();
  informationStore.closeAlert();
}

// Restart the close timer for every Alert, including consecutive Alerts.
watch(
  () => informationStore.intAlertRevision,
  () => {
    clearCloseAlertTimer();
    if (!informationStore.showAlert) return;

    timeoutCloseAlert = setTimeout(() => {
      timeoutCloseAlert = undefined;
      informationStore.closeAlert();
    }, 3000);
  },
);

onBeforeUnmount(clearCloseAlertTimer);
</script>

<style scoped>
:deep(.v-alert__content) {
  min-width: 0;
}

.alert-message {
  max-height: min(160px, 25vh);
  overflow-y: auto;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}
</style>
