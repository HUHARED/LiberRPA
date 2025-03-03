<!-- FileName: SettingArea.vue -->
<template>
  <v-container class="pa-0 ma-0 border-b-thin">
    <v-label class="pa-2 ma-0 text-center" style="display: block">Setting</v-label>

    <v-switch
      v-model="settingStore.executeMode"
      true-value="Debug"
      false-value="Run"
      :label="`Execute mode: ${settingStore.executeMode.toString()}`"
      hide-details
      class="pa-1 ma-0"
      density="compact"
      prepend-icon="mdi-menu-right-outline"></v-switch>
  </v-container>
</template>

<script setup lang="ts">
import { watch } from "vue";
import { updateLocalData } from "../commonFunc";
import { useSettingStore } from "../store";

const settingStore = useSettingStore();

watch(
  () => settingStore.executeMode,
  () => {
    updateLocalData(null, settingStore.executeMode, null, null, null, null, null);
  }
);
</script>

<style scoped></style>
