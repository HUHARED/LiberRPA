<!-- FileName: LogAndTimeSettings.vue -->
<template>
  <v-container fluid class="pa-2 ma-0 flex-row">
    <v-icon
      class="pa-0 ma-0 mt-2 mr-2"
      color="medium-emphasis"
      icon="mdi-open-in-new"></v-icon>

    <v-btn variant="tonal" @click="openProjectLogFolder()">Open Log Folder</v-btn>

    <v-text-field
      id="project-log-folder-path"
      v-model="strProjectLogFolderPath"
      class="pa-0 ma-0 ml-2 mr-2 cursor-pointer"
      density="compact"
      variant="underlined"
      hide-details
      type="text"
      @click="settingStore.selectNewProjectLogFolderPath()">
      <v-tooltip activator="parent" location="bottom">
        <div>
          Click to select the folder used for run logs.
          <br />
          Existing logs will not be moved.
          <br />
          The default folder follows basic.jsonc on the current computer.
        </div>
      </v-tooltip>
    </v-text-field>

    <v-btn
      variant="tonal"
      :disabled="settingStore.projectLogFolderPath === ''"
      @click="settingStore.useDefaultProjectLogFolderPath()">
      Use Default
    </v-btn>
  </v-container>

  <v-container fluid class="pa-2 ma-0 flex-row">
    <v-icon
      class="pa-0 ma-0 mt-2 mr-2"
      color="medium-emphasis"
      icon="mdi-map-clock-outline"></v-icon>

    <v-text-field
      class="clean-space ml-1"
      density="compact"
      hide-details
      variant="plain"
      readonly
      spellcheck="false"
      max-width="110"
      model-value="Time Zone:">
      <v-tooltip activator="parent" location="bottom">
        <div>
          Controls displayed times and the trigger time zone for all local Schedules.
        </div>
      </v-tooltip>
    </v-text-field>

    <v-autocomplete
      v-model="settingStore.timezone"
      variant="underlined"
      class="clean-space"
      density="compact"
      hide-details
      max-width="400"
      :items="arrTimezone"></v-autocomplete>
  </v-container>
</template>

<script setup lang="ts">
import { computed, watch } from "vue";

import { arrTimezone } from "../../Common/time";
import { invokeMain } from "../../IPC/ipc";
import { loggerRenderer } from "../../Logging/logger";
import { useSettingStore } from "../../Store/settingStore";
import { useScheduleStore } from "../../Store/scheduleStore";
import { getErrorMessage } from "../../../../shared/error";

const scheduleStore = useScheduleStore();
const settingStore = useSettingStore();

watch(
  () => settingStore.timezone,
  () => {
    scheduleStore.resetScheduleDialogs();
  },
);

const strProjectLogFolderPath = computed<string>({
  get() {
    return settingStore.projectLogFolderPath || settingStore.defaultProjectLogFolderPath;
  },
  set(newValue: string) {
    settingStore.projectLogFolderPath = newValue;
  },
});

function openProjectLogFolder(): void {
  invokeMain("openProjectLogFolder").catch((e: unknown) => {
    loggerRenderer.error(`Failed to open Project log folder: ${getErrorMessage(e)}`);
  });
}
</script>

<style scoped>
:deep(#project-log-folder-path) {
  cursor: pointer;
}
</style>
