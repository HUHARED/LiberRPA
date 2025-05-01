<!-- FileName: SettingArea.vue -->
<template>
  <v-container class="clean-space" style="height: 300px">
    <v-label class="area-header"> Settings </v-label>

    <v-number-input
      v-model="intMatchTimeout"
      class="clean-space mb-2"
      style="width: 250px"
      control-variant="default"
      :min="3"
      :max="60"
      :precision="0"
      label="Match timeout"
      prepend-icon="mdi-timer-stop-outline"
      suffix="seconds"
      density="compact"
      variant="underlined"
      hide-details>
      <v-tooltip activator="parent" location="bottom">
        <div>
          The timeout for matching element by selector.<br />
          It should be an integer between 3 and 60.
        </div>
      </v-tooltip>
    </v-number-input>

    <v-number-input
      v-model="intIndicateDelay"
      class="clean-space"
      style="width: 250px"
      control-variant="default"
      :min="1"
      :max="10"
      :precision="0"
      label="Indicate delay"
      prepend-icon="mdi-timer-pause-outline"
      suffix="seconds"
      density="compact"
      variant="underlined"
      hide-details>
      <v-tooltip activator="parent" location="bottom">
        <div>
          The delay for indicating element.<br />
          It should be an integer between 1 and 10.
        </div>
      </v-tooltip>
    </v-number-input>

    <v-tooltip text="Use index or path to locate the target HTML element." location="top">
      <template #activator="{ props }">
        <v-switch
          v-model="settingStore.indexOrPath"
          color="blue"
          :label="`LocateHTML: ${settingStore.indexOrPath}`"
          true-value="path"
          false-value="index"
          hide-details
          v-bind="props"
          prepend-icon="mdi-map-marker-star-outline"
          false-icon="mdi-numeric"
          true-icon="mdi-map-marker-path"
          density="compact">
        </v-switch>
      </template>
    </v-tooltip>

    <v-tooltip
      text="Whether grayscale when locating the target image element."
      location="top">
      <template #activator="{ props }">
        <!-- true-value and false-value should not use for a bool value -->
        <v-switch
          v-model="settingStore.grayscale"
          color="gray"
          :label="`grayscale : ${settingStore.grayscale}`"
          hide-details
          v-bind="props"
          prepend-icon="mdi-view-carousel-outline"
          false-icon="mdi-palette"
          true-icon="mdi-gradient-vertical"
          density="compact">
        </v-switch>
      </template>
    </v-tooltip>

    <v-number-input
      v-model="floatConfidence"
      class="clean-space mt-1"
      style="width: 250px"
      control-variant="default"
      :min="0.1"
      :max="0.999"
      :precision="3"
      :step="0.1"
      label="Confidence"
      prepend-icon="mdi-image-filter-center-focus-strong-outline"
      density="compact"
      variant="underlined"
      hide-details>
      <v-tooltip activator="parent" location="bottom">
        <div>
          'confidence' will specify the accuracy when locating the target image element on
          screen.<br />
          It should be a float between 0.1 and 0.999.
        </div>
      </v-tooltip>
    </v-number-input>

    <v-tooltip location="top">
      <template #activator="{ props }">
        <v-switch
          v-model="settingStore.minimizeWindow"
          color="blue"
          :label="`Minimize ：${settingStore.minimizeWindow}`"
          hide-details
          v-bind="props"
          prepend-icon="mdi-arrow-collapse"
          false-icon="mdi-window-restore"
          true-icon="mdi-window-minimize"
          density="compact">
        </v-switch>
      </template>

      <div>
        Whether minimizing Ui Analyzer's window when indicating or validating an
        element(excluding indicating image).<br />
        You can config its default value in 'LiberRPA/configFiles/basic.jsonc'.
      </div>
    </v-tooltip>

    <v-tooltip location="top">
      <template #activator="{ props }">
        <v-switch
          v-model="settingStore.theme"
          color="grey"
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

      <div>
        Modify the UI theme.<br />
        You can config its default value in 'LiberRPA/configFiles/basic.jsonc'.
      </div>
    </v-tooltip>
  </v-container>
</template>

<script setup lang="ts">
import { VNumberInput } from "vuetify/labs/VNumberInput";
import { computed } from "vue";

import { useSettingStore, useInformationStore } from "../store";

const settingStore = useSettingStore();
const informationStore = useInformationStore();

const intMatchTimeout = computed<number>({
  get() {
    return settingStore.intMatchTimeoutSeconds;
  },
  set(newValue: number | null) {
    if (newValue === null) {
      informationStore.showAlertMessage(`It's not an integer between 3 and 60.`);
      return;
    }
    if (newValue >= 3 && newValue <= 60) {
      settingStore.intMatchTimeoutSeconds = newValue;
    }
  },
});

const intIndicateDelay = computed<number>({
  get() {
    return settingStore.intIndicateDelaySeconds;
  },
  set(newValue: number | null) {
    if (newValue === null) {
      informationStore.showAlertMessage(`It's not an integer between 1 and 10.`);
      return;
    }
    if (newValue >= 1 && newValue <= 10) {
      settingStore.intIndicateDelaySeconds = newValue;
    }
  },
});

const floatConfidence = computed<number>({
  get() {
    return settingStore.confidence;
  },
  set(newValue: number | null) {
    if (newValue === null) {
      informationStore.showAlertMessage(`It's not a float between 0.1 and 0.999.`);
      return;
    }
    if (newValue >= 0.1 && newValue <= 0.999) {
      settingStore.confidence = newValue;
    }
  },
});
</script>

<style scoped></style>
