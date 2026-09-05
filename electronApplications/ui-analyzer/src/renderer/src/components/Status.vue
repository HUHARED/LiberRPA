<!-- FileName: Status.vue -->
<template>
  <v-container class="clean-space flex-column" style="height: 140px">
    <v-label class="area-header"> Status </v-label>

    <v-text-field
      :model-value="operationStore.processDescription"
      class="pa-1 ma-0"
      density="compact"
      variant="plain"
      hide-details
      readonly>
      <template #prepend-inner>
        <v-icon
          :color="operationStore.isBusy ? 'info' : 'success'"
          :icon="operationStore.isBusy ? 'mdi-dots-circle' : 'mdi-check-circle-outline'"
          class="clean-space" />
      </template>
    </v-text-field>

    <v-text-field
      v-model="informationStore.information"
      class="pa-1 ma-0"
      label="Process Information"
      variant="underlined"
      density="compact"
      hide-details
      readonly>
      <v-tooltip activator="parent" location="top">
        {{ informationStore.information }}
      </v-tooltip>
    </v-text-field>
  </v-container>
</template>

<script setup lang="ts">
import { useInformationStore, useOperationStore } from "../store";

const informationStore = useInformationStore();
const operationStore = useOperationStore();
</script>

<style scoped></style>
