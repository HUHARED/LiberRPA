<template>
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

  <v-container fluid class="pa-2 ma-0 flex-row">
    <v-tooltip activator="parent" location="bottom">
      <div>
        Delete run videos older than the configured retention period.<br />
        Minimum: 1 day.<br />
        Checked after a run ends, at most once per hour.
      </div>
    </v-tooltip>

    <v-icon class="pa-0 ma-0 mt-2 mr-2" color="grey" icon="mdi-video-off-outline"> </v-icon>

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
</template>

<script setup lang="ts">
import { computed } from "vue";

import { useInformationStore } from "../../Store/informationStore";
import { useSettingStore } from "../../Store/settingStore";

const informationStore = useInformationStore();
const settingStore = useSettingStore();

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
</script>

<style scoped></style>
