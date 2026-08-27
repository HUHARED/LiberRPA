<!-- FileName: LogAndTimeSettings.vue -->
<template>
  <v-container fluid class="pa-2 ma-0 flex-row">
    <v-icon class="pa-0 ma-0 mt-2 mr-2" color="grey" icon="mdi-open-in-new"> </v-icon>

    <v-btn variant="tonal" @click="openProjectLogFolder()"> Open Log Folder </v-btn>

    <v-text-field
      id="project-log-folder-path"
      v-model="strProjectLogFolderPath"
      style="cursor: pointer !important"
      class="pa-0 ma-0 ml-2 mr-2"
      density="compact"
      variant="underlined"
      hide-details
      type="text"
      @click="settingStore.selectNewProjectLogFolderPath()">
      <v-tooltip activator="parent" location="bottom">
        <div>
          Click to select the folder used for run logs.<br />
          Existing logs will not be moved.<br />
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
    <v-icon class="pa-0 ma-0 mt-2 mr-2" color="grey" icon="mdi-map-clock-outline"> </v-icon>

    <v-text-field
      class="clean-space ml-1"
      density="compact"
      hide-details
      variant="plain"
      readonly
      spellcheck="false"
      style="max-width: 110px"
      model-value="Time Zone:">
      <v-tooltip activator="parent" location="bottom">
        <div>
          Controls how Executor displays time and interprets Cron expressions and active
          periods.<br />
          Changing it recalculates pending runs.
        </div>
      </v-tooltip>
    </v-text-field>

    <v-autocomplete
      v-model="settingStore.timezone"
      variant="underlined"
      class="clean-space"
      density="compact"
      hide-details
      style="max-width: 400px"
      :items="arrTimezone">
    </v-autocomplete>
  </v-container>
</template>

<script setup lang="ts">
import { computed } from "vue";

import { arrTimezone } from "../../Common/time";
import { invokeMain } from "../../IPC/ipc";
import { loggerRenderer } from "../../Logging/logger";
import { useSettingStore } from "../../Store/settingStore";

const settingStore = useSettingStore();

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
    loggerRenderer.error(`Failed to open Project log folder: ${String(e)}`);
  });
}
</script>

<style scoped>
:deep(#project-log-folder-path) {
  cursor: pointer;
}
</style>
