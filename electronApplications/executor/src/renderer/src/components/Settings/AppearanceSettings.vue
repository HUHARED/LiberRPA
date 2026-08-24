<template>
  <v-container fluid class="pa-2 ma-0">
    <v-tooltip text="Modify the UI theme." location="bottom">
      <template #activator="{ props }">
        <v-switch
          v-model="settingStore.theme"
          :label="`Theme: ${settingStore.theme === 'dark' ? 'Dark' : 'Light'}`"
          true-value="dark"
          false-value="light"
          hide-details
          v-bind="props"
          prepend-icon="mdi-theme-light-dark"
          false-icon="mdi-white-balance-sunny"
          true-icon="mdi-weather-night"
          density="compact">
        </v-switch>
      </template>
    </v-tooltip>
  </v-container>
</template>

<script setup lang="ts">
import { useSettingStore } from "../../Store/settingStore";

const settingStore = useSettingStore();
</script>

<style scoped></style>
