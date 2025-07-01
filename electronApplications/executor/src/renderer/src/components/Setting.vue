<!-- FileName: Setting.vue -->
<template>
  <v-container fluid class="clean-space flex-row-grow-1 fill-height flex-column">
    <v-label class="header-label tab-header">Setting</v-label>

    <!-- Use a container to make the v-switch to left -->
    <v-container fluid class="pa-2 ma-0">
      <v-tooltip text="Modify the UI theme." location="bottom">
        <template #activator="{ props }">
          <v-switch
            v-model="settingStore.theme"
            :label="`Theme ：${settingStore.theme}`"
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

    <v-container fluid class="pa-2 ma-0">
      <v-tooltip location="bottom">
        <template #activator="{ props }">
          <v-switch
            v-model="settingStore.keepRdpSession"
            :label="`Keep RDP Session ：${settingStore.keepRdpSession}`"
            hide-details
            v-bind="props"
            prepend-icon="mdi-account-lock-open-outline"
            true-icon="mdi-lock-open-variant-outline"
            density="compact">
          </v-switch>
        </template>

        <div>
          Keep GUI active if you use RDP and it was disconnected.<br />
          Must run Executor as administrator.<br />
          Executor will shake the mouse if the mouse didn't move during previous 30 seconds
          to avoid screen lock, but can't prevent other lock behavior.<br />
          (May not work if the computer has no Virtual Display Driver or multiple users are
          using it.)
        </div>
      </v-tooltip>
    </v-container>

    <!-- v-checkbox-btn in <template #prepend-inner> has some bugs: color and icon can't be controled, so combine several components into a new one -->

    <!-- RDP Session Width -->
    <v-container fluid class="pa-2 ma-0 flex-row">
      <v-tooltip activator="parent" location="bottom">
        <div>
          The width when RDP disconnected.<br />
          Minimum: 480, Maximum: 7680.
        </div>
      </v-tooltip>

      <v-icon
        class="pa-0 ma-0 mt-2 ml-12 mr-2"
        color="grey"
        icon="mdi-arrow-split-vertical">
      </v-icon>

      <v-text-field
        class="clean-space"
        density="compact"
        hide-details
        variant="plain"
        readonly
        spellcheck="false"
        style="max-width: 210px"
        :value="`Session window width:`">
      </v-text-field>

      <v-number-input
        v-model="intKeepRdpSessionWidth"
        class="pa-0 ma-0 ml-2"
        density="compact"
        hide-details
        control-variant="stacked"
        inset
        :min="480"
        :max="7680"
        :precision="0"
        style="max-width: 100px"
        :disabled="!settingStore.keepRdpSession">
      </v-number-input>

      <span class="pa-0 ma-0 mt-2">px.</span>
    </v-container>

    <!-- RDP Session Height -->
    <v-container fluid class="pa-2 ma-0 flex-row">
      <v-tooltip activator="parent" location="bottom">
        <div>
          The height when RDP disconnected.<br />
          Minimum: 480, Maximum: 7680.
        </div>
      </v-tooltip>
      <v-icon
        class="pa-0 ma-0 mt-2 ml-12 mr-2"
        color="grey"
        icon="mdi-arrow-split-horizontal">
      </v-icon>

      <v-text-field
        class="clean-space"
        density="compact"
        hide-details
        variant="plain"
        readonly
        spellcheck="false"
        style="max-width: 210px"
        :value="`Session window height:`">
      </v-text-field>

      <v-number-input
        v-model="intKeepRdpSessionHeight"
        class="pa-0 ma-0 ml-2"
        density="compact"
        hide-details
        control-variant="stacked"
        inset
        :min="480"
        :max="7680"
        :precision="0"
        style="max-width: 100px"
        :disabled="!settingStore.keepRdpSession">
      </v-number-input>

      <span class="pa-0 ma-0 mt-2">px.</span>
    </v-container>

    <!-- Log timeout -->
    <v-container fluid class="pa-2 ma-0 flex-row">
      <v-tooltip activator="parent" location="bottom">
        <div>
          The timeout for cleaning project running log folders (include logs and videos).<br />
          It should be greater than 7.<br />
          You can enable it or not.<br />
          (It will be checked after a task end with a minimum interval of one hour.)
        </div>
      </v-tooltip>

      <v-icon class="pa-0 ma-0 mt-2 mr-2" color="grey" icon="mdi-delete-clock-outline">
      </v-icon>

      <v-checkbox
        v-model="settingStore.logTimeoutEnable"
        class="clean-space"
        density="compact"
        :label="`\u00A0\u00A0Log folders retention time:`"
        hide-details>
      </v-checkbox>

      <v-number-input
        v-model="intLogTimeoutDays"
        class="pa-0 ma-0 ml-2"
        density="compact"
        hide-details
        control-variant="stacked"
        inset
        :min="7"
        :precision="0"
        style="max-width: 100px"
        :disabled="!settingStore.logTimeoutEnable">
      </v-number-input>

      <span class="pa-0 ma-0 mt-2">days.</span>
    </v-container>

    <!-- Log video timeout -->
    <v-container fluid class="pa-2 ma-0 flex-row">
      <v-tooltip activator="parent" location="bottom">
        <div>
          The timeout for cleaning project running videos.<br />
          It should be greater than 1.<br />
          You can enable it or not.<br />
          (It will be checked after a task end with a minimum interval of one hour.)
        </div>
      </v-tooltip>

      <v-icon class="pa-0 ma-0 mt-2 mr-2" color="grey" icon="mdi-video-off-outline">
      </v-icon>

      <v-checkbox
        v-model="settingStore.videoTimeoutEnable"
        class="clean-space"
        density="compact"
        :label="`\u00A0\u00A0Log videos \u00A0retention time:`"
        hide-details>
      </v-checkbox>

      <v-number-input
        v-model="intVideoTimeoutDays"
        class="pa-0 ma-0 ml-2"
        density="compact"
        hide-details
        control-variant="stacked"
        inset
        :min="1"
        :precision="0"
        style="max-width: 100px"
        :disabled="!settingStore.videoTimeoutEnable">
      </v-number-input>

      <span class="pa-0 ma-0 mt-2">days.</span>
    </v-container>

    <!-- Log video maximum size -->
    <v-container fluid class="pa-2 ma-0 flex-row">
      <v-tooltip activator="parent" location="bottom">
        <div>
          The size threshold for cleaning project running videos.<br />
          It should be greater than 1.<br />
          You can enable it or not.<br />
          (It will be checked after a task end with a minimum interval of one hour.)
        </div>
      </v-tooltip>

      <v-icon class="pa-0 ma-0 mt-2 mr-2" color="grey" icon="mdi-video-minus-outline">
      </v-icon>

      <v-checkbox
        v-model="settingStore.videoSizeEnable"
        class="clean-space"
        density="compact"
        :label="`\u00A0\u00A0Log videos \u00A0retention size:`"
        hide-details>
      </v-checkbox>

      <v-number-input
        v-model="intVideoSizeGB"
        class="pa-0 ma-0 ml-2"
        density="compact"
        hide-details
        control-variant="stacked"
        inset
        :min="1"
        :precision="0"
        style="max-width: 100px"
        :disabled="!settingStore.videoSizeEnable">
      </v-number-input>

      <span class="pa-0 ma-0 mt-2">GB.</span>
    </v-container>

    <!-- Project Log Folder -->
    <v-container fluid class="pa-2 ma-0 flex-row">
      <v-icon class="pa-0 ma-0 mt-2 mr-2" color="grey" icon="mdi-open-in-new"> </v-icon>

      <v-btn
        variant="tonal"
        @click="sendMain('send:open-project-log-folder-path', strProjectLogFolderPath)">
        Open Project Log Folder
      </v-btn>

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
            Click to select a folder to save project logs.<br />
            (Already existing logs will not be moved.)<br />
            (Check whether the path is what you want if the Executor is copied from another
            computer.)
          </div>
        </v-tooltip>
      </v-text-field>
    </v-container>

    <!-- Time Zone -->
    <v-container fluid class="pa-2 ma-0 flex-row">
      <v-icon class="pa-0 ma-0 mt-2 mr-2" color="grey" icon="mdi-map-clock-outline">
      </v-icon>

      <v-text-field
        class="clean-space ml-1"
        density="compact"
        hide-details
        variant="plain"
        readonly
        spellcheck="false"
        style="max-width: 110px"
        :value="`Time zone:`">
        <v-tooltip activator="parent" location="bottom">
          <div>
            (Not work yet) LiberRPA Console needs it to convert time of Executor.<br />
          </div>
        </v-tooltip>
      </v-text-field>

      <v-select
        v-model="settingStore.timezone"
        variant="underlined"
        class="clean-space"
        density="compact"
        hide-details
        style="max-width: 400px"
        :items="arrTimezone">
      </v-select>
    </v-container>
  </v-container>
</template>

<script setup lang="ts">
import { VNumberInput } from "vuetify/labs/VNumberInput";

import { watch, computed } from "vue";
import { debounce } from "lodash";
import { tz } from "moment-timezone";

import { loggerRenderer, sendMain } from "../ipcOfRenderer";
import { useSettingStore, useInformationStore } from "../store";
import { DictExecutorConfig } from "../../../shared/interface";

const arrTimezone = tz.names();

const settingStore = useSettingStore();
const informationStore = useInformationStore();

const intKeepRdpSessionWidth = computed<number>({
  get() {
    return settingStore.keepRdpSessionWidth;
  },
  set(newValue: number | null) {
    if (newValue === null) {
      informationStore.showAlertMessage(
        `It's not an integer between 480 and 7680. (${newValue})`
      );
      return;
    }

    if (newValue >= 480 && newValue <= 7680) {
      settingStore.keepRdpSessionWidth = newValue;
    }
  },
});

const intKeepRdpSessionHeight = computed<number>({
  get() {
    return settingStore.keepRdpSessionHeight;
  },
  set(newValue: number | null) {
    if (newValue === null) {
      informationStore.showAlertMessage(
        `It's not an integer between 480 and 7680. (${newValue})`
      );
      return;
    }

    if (newValue >= 480 && newValue <= 7680) {
      settingStore.keepRdpSessionHeight = newValue;
    }
  },
});

const intLogTimeoutDays = computed<number>({
  get() {
    return settingStore.logTimeoutDays;
  },
  set(newValue: number | null) {
    if (newValue === null) {
      informationStore.showAlertMessage(`It's not an integer >= 7. (${newValue})`);
      return;
    }

    if (newValue >= 7) {
      settingStore.logTimeoutDays = newValue;
    }
  },
});

const intVideoTimeoutDays = computed<number>({
  get() {
    return settingStore.videoTimeoutDays;
  },
  set(newValue: number | null) {
    if (newValue === null) {
      informationStore.showAlertMessage(`It's not an integer >= 1. (${newValue})`);
      return;
    }

    if (newValue >= 1) {
      settingStore.videoTimeoutDays = newValue;
    }
  },
});

const intVideoSizeGB = computed<number>({
  get() {
    return settingStore.videoSizeGB;
  },
  set(newValue: number | null) {
    if (newValue === null) {
      informationStore.showAlertMessage(`It's not an integer >= 1. (${newValue})`);
      return;
    }

    if (newValue >= 1) {
      settingStore.videoSizeGB = newValue;
    }
  },
});

const strProjectLogFolderPath = computed<string>({
  get() {
    return settingStore.projectLogFolderPath;
  },
  set(newValue: string) {
    settingStore.projectLogFolderPath = newValue;
  },
});

// Define the debounced update function once
const debouncedUpdate = debounce(() => {
  loggerRenderer.info(`Modified setting: ${JSON.stringify(settingStore.$state)}`);
  saveConfig();
}, 300);

watch(
  () => settingStore.$state,
  () => {
    // console.log("!!update");

    debouncedUpdate();
  },
  { deep: true }
);

function saveConfig(): void {
  const dictConfigExecutor: DictExecutorConfig = {
    theme: settingStore.theme,
    keepRdpSession: settingStore.keepRdpSession,
    keepRdpSessionWidth: settingStore.keepRdpSessionWidth,
    keepRdpSessionHeight: settingStore.keepRdpSessionHeight,
    logTimeoutEnable: settingStore.logTimeoutEnable,
    logTimeoutDays: settingStore.logTimeoutDays,
    videoTimeoutEnable: settingStore.videoTimeoutEnable,
    videoTimeoutDays: settingStore.videoTimeoutDays,
    videoSizeEnable: settingStore.videoSizeEnable,
    videoSizeGB: settingStore.videoSizeGB,
    projectLogFolderPath: settingStore.projectLogFolderPath,
    timezone: settingStore.timezone,
  };

  sendMain("send:save-executor-config", dictConfigExecutor);
}
</script>

<style scoped>
:deep(#project-log-folder-path) {
  cursor: pointer;
}
</style>
