<!-- FileName: ElementHierarchy.vue -->
<template>
  <v-container class="clean-space flex-column-grow-1 flex-column">
    <v-label class="area-header"> Element Hierarchy </v-label>

    <!-- Show tip card when have no element. -->
    <v-card
      v-if="selectorStore.arrEleHierarchy.length === 0"
      class="ma-1"
      text="Indicate or validate an element to show its Element Hierarchy."></v-card>

    <v-list
      v-else
      class="clean-space flex-column-grow-1"
      lines="one"
      density="compact"
      slim>
      <v-list-item
        v-for="(item, index) in selectorStore.arrEleHierarchy"
        :key="index"
        :value="item"
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
        <v-list-item-title @click="selectorStore.refreshArrtibuteEditor(index)">
          {{ JSON.stringify(item) }}
        </v-list-item-title>
      </v-list-item>
    </v-list>
  </v-container>
</template>

<script setup lang="ts">
import { watch } from "vue";

import { loggerRenderer } from "../ipcOfRenderer";
import { useSelectorStore, useInformationStore, useSettingStore } from "../store";

const selectorStore = useSelectorStore();
const informationStore = useInformationStore();
const settingStore = useSettingStore();

watch(
  () => informationStore.information,
  () => {
    /* loggerRenderer.debug(
      `watch informationStore.information:\n${informationStore.information}`
    ); */

    // If it it a selector json.
    if (informationStore.information.startsWith('{"selector"')) {
      selectorStore.afterIndicate();
      // Reset validateState
      informationStore.validateState = undefined;
      settingStore.toggleWindow();
    } else if (informationStore.information.startsWith('{"validate"')) {
      // If it is element validation.

      const boolResult = JSON.parse(informationStore.information)["validate"];
      loggerRenderer.debug("boolResult=" + boolResult);
      informationStore.validateState = boolResult;
      settingStore.toggleWindow();
    } else {
      loggerRenderer.debug("It's not a known expected result.");
      // Reset validateState
      informationStore.validateState = undefined;
    }
  }
);
</script>

<style scoped></style>
