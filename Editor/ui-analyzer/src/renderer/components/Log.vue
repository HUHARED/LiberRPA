<!-- FileName: Log.vue -->
<template>
  <v-container class="clean-space flex-column" style="height: 140px">
    <v-label class="header-label"> Log </v-label>

    <v-btn
      @click="sendIpcMessageToMain('cmd-open-log-path')"
      class="w-100"
      prepend-icon="mdi-open-in-new"
      density="compact"
      variant="tonal"
    >
      Open log file
      <v-tooltip activator="parent" location="bottom">
        {{ settingStore.strLogPath }}
      </v-tooltip></v-btn
    >

    <v-text-field
      class="pa-1 ma-0"
      density="compact"
      hide-details
      readonly
      variant="plain"
      v-model="selectorStore.processDescription"
    >
      <template #prepend-inner>
        <v-icon
          :color="selectorStore.processDescription === 'Idle' ? 'success' : 'info'"
          :icon="
            selectorStore.processDescription === 'Idle'
              ? 'mdi-check-circle-outline'
              : 'mdi-dots-circle'
          "
        />
      </template>
    </v-text-field>
    <v-text-field
      class="pa-1 ma-0"
      density="compact"
      hide-details
      readonly
      variant="underlined"
      label="Process Information"
      v-model="informationStore.information"
    >
      <v-tooltip activator="parent" location="top">
        {{ informationStore.information }}</v-tooltip
      >
    </v-text-field>
  </v-container>
</template>

<script setup lang="ts">
import { sendIpcMessageToMain } from "../ipcOfRenderer";
import { useSelectorStore, useSettingStore, useInformationStore } from "../store";
const selectorStore = useSelectorStore();
const settingStore = useSettingStore();
const informationStore = useInformationStore();
</script>

<style scoped></style>
