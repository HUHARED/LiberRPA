<!-- FileName: BuildinPrjArgs.vue -->
<template>
  <v-container class="pa-0 ma-0 border-b-thin">
    <v-label class="pa-2 ma-0 text-center" style="display: block"
      >Build-in Project Arguments</v-label
    >

    <v-tooltip text="Set the minimum log level." location="top">
      <template #activator="{ props }">
        <v-select
          label="Log Level"
          prepend-icon="mdi-database-edit-outline"
          variant="underlined"
          class="pa-1 ma-0 mb-2"
          v-model="argsStore.logLevel"
          density="compact"
          hide-details
          v-bind="props"
          :items="['VERBOSE', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']">
        </v-select>
      </template>
    </v-tooltip>

    <v-tooltip text="Whether recording vedio when the process running." location="top">
      <template #activator="{ props }">
        <v-switch
          v-model="argsStore.recordVideo"
          :label="`Record video ：${argsStore.recordVideo.toString()}`"
          hide-details
          v-bind="props"
          class="pa-1 ma-0"
          density="compact"
          prepend-icon="mdi-video-outline"></v-switch>
      </template>
    </v-tooltip>

    <v-tooltip text="Forcibly stop the process by Ctrl+F12." location="top">
      <template #activator="{ props }">
        <v-switch
          v-model="argsStore.stopShortcut"
          :label="`Stop shortcut: ${argsStore.stopShortcut.toString()}`"
          hide-details
          v-bind="props"
          class="pa-1 ma-0"
          density="compact"
          prepend-icon="mdi-stop-circle-outline">
        </v-switch>
      </template>
    </v-tooltip>

    <v-tooltip text="Highlight a UI element before manipulating it. (Few UI functions are invalid.)" location="top">
      <template #activator="{ props }">
        <v-switch
          v-model="argsStore.highlightUi"
          :label="`Highlight UI ：${argsStore.highlightUi.toString()}`"
          hide-details
          v-bind="props"
          class="pa-1 ma-0"
          density="compact"
          prepend-icon="mdi-rectangle-outline">
        </v-switch>
      </template>
    </v-tooltip>
  </v-container>
</template>

<script setup lang="ts">
import { watch } from "vue";
import { updateLocalData } from "../commonFunc";
import { useArgsStore } from "../store";

const argsStore = useArgsStore();

watch(
  () => argsStore.logLevel,
  () => {
    updateLocalData(null, null, argsStore.logLevel, null, null, null, null);
  }
);

watch(
  () => argsStore.recordVideo,
  () => {
    updateLocalData(null, null, null, argsStore.recordVideo, null, null, null);
  }
);

watch(
  () => argsStore.stopShortcut,
  () => {
    updateLocalData(null, null, null, null, argsStore.stopShortcut, null, null);
  }
);

watch(
  () => argsStore.highlightUi,
  () => {
    updateLocalData(null, null, null, null, null, argsStore.highlightUi, null);
  }
);
</script>

<style scoped></style>
