<!-- FileName: Alert.vue -->
<template>
  <v-alert
    v-if="informationStore.showAlert"
    :text="informationStore.information"
    @click:close="clearInformation"
    variant="flat"
    type="warning"
    closable
  >
  </v-alert>
</template>

<script setup lang="ts">
import { watch } from "vue";
import { useInformationStore } from "../store";
const informationStore = useInformationStore();

function clearInformation() {
  informationStore.information = "...";
  informationStore.showAlert = false;
}

// Close the alert after 3 seconds.
watch(
  () => informationStore.showAlert,
  (newValue) => {
    if (newValue === true) {
      setTimeout(() => {
        clearInformation();
      }, 3000);
    }
  }
);
</script>

<style scoped></style>
