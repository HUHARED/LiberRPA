<template>
  <v-container fluid class="clean-space flex-row-grow-1 fill-height flex-column">
    <v-label class="header-label tab-header">Settings</v-label>

    <!-- Use a container to make the v-switch to left -->
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

    <v-container fluid class="pa-2 ma-0">
      <v-tooltip location="bottom">
        <template #activator="{ props }">
          <v-switch
            v-model="settingStore.keepRdpSession"
            label="Keep RDP Session"
            hide-details
            v-bind="props"
            prepend-icon="mdi-account-lock-open-outline"
            true-icon="mdi-lock-open-variant-outline"
            density="compact">
          </v-switch>
        </template>

        <div>
          Keep the GUI session active after an RDP connection is disconnected.<br />
          Executor must run as administrator.<br />
          If the mouse has not moved for 30 seconds, Executor moves it to help prevent the
          screen from locking. This cannot prevent every type of session lock.<br />
          (May not work without a Virtual Display Driver or when multiple users are active.)
        </div>
      </v-tooltip>
    </v-container>

    <!-- v-checkbox-btn in <template #prepend-inner> has some bugs: color and icon can't be controled, so combine several components into a new one -->

    <!-- RDP Session Width -->
    <v-container fluid class="pa-2 ma-0 flex-row">
      <v-tooltip activator="parent" location="bottom">
        <div>
          Session width after RDP is disconnected.<br />
          Range: 480–7680 px.
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
        model-value="Session Width">
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

      <span class="pa-0 ma-0 mt-2">px</span>
    </v-container>

    <!-- RDP Session Height -->
    <v-container fluid class="pa-2 ma-0 flex-row">
      <v-tooltip activator="parent" location="bottom">
        <div>
          Session height after RDP is disconnected.<br />
          Range: 480–7680 px.
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
        model-value="Session Height">
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

      <span class="pa-0 ma-0 mt-2">px</span>
    </v-container>

    <!-- Log timeout -->
    <v-container fluid class="pa-2 ma-0 flex-row">
      <v-tooltip activator="parent" location="bottom">
        <div>
          Delete run log folders older than the configured retention period, including logs
          and videos.<br />
          Minimum: 7 days.<br />
          Checked after a run ends, at most once per hour.
        </div>
      </v-tooltip>

      <v-icon class="pa-0 ma-0 mt-2 mr-2" color="grey" icon="mdi-delete-clock-outline">
      </v-icon>

      <v-checkbox
        v-model="settingStore.logTimeoutEnable"
        class="clean-space"
        density="compact"
        label="Run Log Retention"
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

      <span class="pa-0 ma-0 mt-2">days</span>
    </v-container>

    <!-- Log video timeout -->
    <v-container fluid class="pa-2 ma-0 flex-row">
      <v-tooltip activator="parent" location="bottom">
        <div>
          Delete run videos older than the configured retention period.<br />
          Minimum: 1 day.<br />
          Checked after a run ends, at most once per hour.
        </div>
      </v-tooltip>

      <v-icon class="pa-0 ma-0 mt-2 mr-2" color="grey" icon="mdi-video-off-outline">
      </v-icon>

      <v-checkbox
        v-model="settingStore.videoTimeoutEnable"
        class="clean-space"
        density="compact"
        label="Video Retention"
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

      <span class="pa-0 ma-0 mt-2">days</span>
    </v-container>

    <!-- Log video maximum size -->
    <v-container fluid class="pa-2 ma-0 flex-row">
      <v-tooltip activator="parent" location="bottom">
        <div>
          Delete the oldest run videos when total video storage exceeds this limit.<br />
          Minimum: 1 GB.<br />
          Checked after a run ends, at most once per hour.
        </div>
      </v-tooltip>

      <v-icon class="pa-0 ma-0 mt-2 mr-2" color="grey" icon="mdi-video-minus-outline">
      </v-icon>

      <v-checkbox
        v-model="settingStore.videoSizeEnable"
        class="clean-space"
        density="compact"
        label="Video Storage Limit"
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

      <span class="pa-0 ma-0 mt-2">GB</span>
    </v-container>

    <!-- Project Log Folder -->
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
  </v-container>
</template>

<script setup lang="ts">
import { watch, computed } from "vue";
import { debounce } from "lodash";

import { invokeMain } from "../IPC/ipc";
import { loggerRenderer } from "../Logging/logger";
import { useInformationStore } from "../Store/informationStore";
import { useSettingStore } from "../Store/settingStore";
import { arrTimezone } from "../Common/time";
import type { DictExecutorConfig } from "../../../shared/interface";

const settingStore = useSettingStore();
const informationStore = useInformationStore();

const intKeepRdpSessionWidth = computed<number>({
  get() {
    return settingStore.keepRdpSessionWidth;
  },
  set(newValue: number | null) {
    if (newValue === null) {
      informationStore.showAlertMessage(
        `It's not an integer between 480 and 7680. (${newValue})`,
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
        `It's not an integer between 480 and 7680. (${newValue})`,
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
    return settingStore.projectLogFolderPath || settingStore.defaultProjectLogFolderPath;
  },
  set(newValue: string) {
    settingStore.projectLogFolderPath = newValue;
  },
});

const dictConfigExecutor = computed<DictExecutorConfig>(() => ({
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
}));

function openProjectLogFolder(): void {
  invokeMain("openProjectLogFolder", strProjectLogFolderPath.value).catch((e: unknown) => {
    loggerRenderer.error(`Failed to open Project log folder: ${String(e)}`);
  });
}

// Define the debounced update function once
const debouncedUpdate = debounce(() => {
  loggerRenderer.info(`Modified setting: ${JSON.stringify(dictConfigExecutor.value)}`);
  saveConfig().catch((e: unknown) => {
    loggerRenderer.error(`Failed to save Executor settings: ${String(e)}`);
  });
}, 300);

watch(dictConfigExecutor, () => {
  debouncedUpdate();
});

async function saveConfig(): Promise<void> {
  await invokeMain("saveExecutorConfig", dictConfigExecutor.value);
}
</script>

<style scoped>
:deep(#project-log-folder-path) {
  cursor: pointer;
}
</style>
