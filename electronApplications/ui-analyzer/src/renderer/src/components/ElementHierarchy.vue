<!-- FileName: ElementHierarchy.vue -->
<template>
  <v-container class="clean-space flex-column-grow-1 flex-column">
    <v-label class="area-header"> Element Hierarchy </v-label>

    <!-- Show tip card when have no element. -->
    <v-card
      v-if="selectorStore.arrEleHierarchy.length === 0"
      class="ma-1"
      text="Indicate or validate an element to show Element Hierarchy.">
    </v-card>

    <v-list
      v-else
      v-model:selected="arrSelectedLayerIndex"
      class="clean-space flex-column-grow-1"
      lines="one"
      density="compact"
      mandatory
      slim>
      <v-list-item
        v-for="(dictAttr, index) in selectorStore.arrEleHierarchy"
        :key="index"
        :value="index"
        color="primary"
        rounded="shaped">
        <!-- Add the checkbox for each layer. When check or uncheck a layer, emit an event. -->
        <template #prepend>
          <v-list-item-action>
            <v-checkbox-btn
              density="compact"
              :model-value="selectorStore.arrLayerCheckState[index]"
              @update:model-value="
                selectorStore.handleLayerCheck(index, $event)
              "></v-checkbox-btn>
          </v-list-item-action>
        </template>

        <!-- Show the value's JSON string of each layer. -->
        <v-list-item-title>
          {{ JSON.stringify(dictAttr) }}
        </v-list-item-title>
      </v-list-item>
    </v-list>
  </v-container>
</template>

<script setup lang="ts">
import { computed } from "vue";

import { useSelectorStore } from "../store";

const selectorStore = useSelectorStore();

const arrSelectedLayerIndex = computed({
  get: (): number[] => {
    return selectorStore.intClickedLayer >= 0 ? [selectorStore.intClickedLayer] : [];
  },
  set: (arrLayerIndex: number[]): void => {
    if (arrLayerIndex.length === 0) return;
    selectorStore.refreshArrtibuteEditor(arrLayerIndex[0]);
  },
});
</script>

<style scoped></style>
