<template>
  <v-alert
    v-if="informationStore.showAlert"
    style="position: fixed; width: 100%; opacity: 0.9; z-index: 9999"
    :text="informationStore.information"
    variant="flat"
    type="warning"
    closable
    @click:close="clearInformation">
  </v-alert>
</template>

<script setup lang="ts">
import { onBeforeUnmount, watch } from "vue";

import { useInformationStore } from "../../Store/informationStore";

const informationStore = useInformationStore();

let timeoutId: ReturnType<typeof setTimeout> | undefined;

function clearAutoCloseTimer(): void {
  if (timeoutId !== undefined) {
    clearTimeout(timeoutId);
    timeoutId = undefined;
  }
}

function clearInformation(): void {
  clearAutoCloseTimer();
  informationStore.showAlert = false;
  informationStore.information = "...";
}

watch(
  () => informationStore.alertRevision,
  () => {
    if (!informationStore.showAlert) {
      return;
    }

    clearAutoCloseTimer();
    timeoutId = setTimeout(() => {
      clearInformation();
    }, 3000);
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  clearAutoCloseTimer();
});
</script>

<style scoped></style>
