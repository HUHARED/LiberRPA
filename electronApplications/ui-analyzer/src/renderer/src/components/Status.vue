<!-- FileName: Status.vue -->
<template>
  <v-container class="clean-space flex-column" style="height: 140px">
    <v-label class="area-header"> Status </v-label>

    <v-text-field
      v-model="selectorStore.processDescription"
      class="pa-1 ma-0"
      density="compact"
      variant="plain"
      hide-details
      readonly>
      <template #prepend-inner>
        <v-icon
          :color="selectorStore.processDescription === 'Idle' ? 'success' : 'info'"
          :icon="
            selectorStore.processDescription === 'Idle'
              ? 'mdi-check-circle-outline'
              : 'mdi-dots-circle'
          "
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
import { useSelectorStore, useInformationStore } from "../store";

const selectorStore = useSelectorStore();
const informationStore = useInformationStore();
</script>

<style scoped></style>
