<!-- FileName: SettingArea.vue -->
<template>
  <v-container class="clean-space" style="height: 300px">
    <v-label class="header-label"> Settings </v-label>

    <v-text-field
      class="clean-space"
      density="compact"
      hide-details
      variant="underlined"
      type="number"
      min="3"
      max="60"
      label="Match timeout"
      v-model="intMatchTimeout"
      :rules="arrTimeoutRules"
      prepend-icon="mdi-timer-stop-outline"
      suffix="seconds"
      style="height: 40px; width: 160px"
    >
      <v-tooltip activator="parent" location="bottom">
        The timeout for matching element by selector. It should be an integer between 3 and
        60.</v-tooltip
      >
    </v-text-field>
    <v-text-field
      class="clean-space"
      density="compact"
      hide-details
      variant="underlined"
      type="number"
      min="1"
      max="10"
      label="Indicate delay"
      v-model="intIndicateDelay"
      :rules="arrDelayRules"
      prepend-icon="mdi-timer-pause-outline"
      suffix="seconds"
      style="height: 40px; width: 160px"
    >
      <v-tooltip activator="parent" location="bottom">
        The delay for indicating element. It should be an integer between 1 and
        10.</v-tooltip
      >
    </v-text-field>

    <v-tooltip text="Use index or path to locate the target HTML element." location="top">
      <template #activator="{ props }">
        <v-switch
          color="blue"
          :label="`LocateHTML: ${settingStore.indexOrPath}`"
          v-model="settingStore.indexOrPath"
          true-value="path"
          false-value="index"
          hide-details
          v-bind="props"
          prepend-icon="mdi-map-marker-star-outline"
          false-icon="mdi-numeric"
          true-icon="mdi-map-marker-path"
          density="compact"
        >
        </v-switch>
      </template>
    </v-tooltip>

    <v-tooltip
      text="Whether grayscale when locating the target image element."
      location="top"
    >
      <template #activator="{ props }">
        <!-- true-value and false-value should not use for a bool value -->
        <v-switch
          color="gray"
          :label="`grayscale : ${settingStore.grayscale}`"
          v-model="settingStore.grayscale"
          hide-details
          v-bind="props"
          prepend-icon="mdi-view-carousel-outline"
          false-icon="mdi-palette"
          true-icon="mdi-gradient-vertical"
          density="compact"
        >
        </v-switch>
      </template>
    </v-tooltip>

    <v-text-field
      class="clean-space"
      density="compact"
      hide-details
      variant="underlined"
      type="number"
      min="0.1"
      max="0.999"
      step="0.1"
      label="confidence"
      v-model="floatConfidence"
      :rules="arrConfidence"
      prepend-icon="mdi-percent-outline"
      style="height: 40px; width: 160px"
    >
      <v-tooltip activator="parent" location="bottom">
        'confidence' will specify the accuracy when locating the target image element on
        screen. It should be a float between 0.1 and 0.999.</v-tooltip
      >
    </v-text-field>

    <v-tooltip
      text="Whether minimizing Ui Analyzer's window when indicating or validating an element(excluding indicating image). You can config its default value in 'LiberRPA/configFiles/basic.jsonc'."
      location="top"
    >
      <template #activator="{ props }">
        <v-switch
          color="blue"
          :label="`Minimize ：${settingStore.minimizeWindow}`"
          v-model="settingStore.minimizeWindow"
          hide-details
          v-bind="props"
          prepend-icon="mdi-arrow-collapse"
          false-icon="mdi-window-restore"
          true-icon="mdi-window-minimize"
          density="compact"
        >
        </v-switch>
      </template>
    </v-tooltip>

    <v-tooltip
      text="Modify the UI theme. You can config its default value in 'LiberRPA/configFiles/basic.jsonc'."
      location="top"
    >
      <template #activator="{ props }">
        <v-switch
          color="grey"
          :label="`Theme ：${settingStore.theme}`"
          v-model="settingStore.theme"
          true-value="dark"
          false-value="light"
          hide-details
          v-bind="props"
          prepend-icon="mdi-theme-light-dark"
          false-icon="mdi-white-balance-sunny"
          true-icon="mdi-weather-night"
          density="compact"
        >
        </v-switch>
      </template>
    </v-tooltip>
  </v-container>
</template>

<script setup lang="ts">
import { loggerRenderer } from "../ipcOfRenderer";
import { ref, watch } from "vue";
import { useSettingStore } from "../store";
const settingStore = useSettingStore();

const intMatchTimeout = ref(settingStore.intMatchTimeoutSeconds);
const intIndicateDelay = ref(settingStore.intIndicateDelaySeconds);
const floatConfidence = ref(settingStore.confidence);

watch(
  () => intMatchTimeout.value,
  (newValue) => {
    // In fact, type of newValue is string. But static check thinks it is number, use toString().
    const numTemp = parseFloat(newValue.toString());

    if (Number.isInteger(numTemp) && numTemp >= 3 && numTemp <= 60) {
      settingStore.intMatchTimeoutSeconds = numTemp;
      loggerRenderer.debug(
        `Modify setting: settingStore.intMatchTimeoutSeconds = ${
          settingStore.intMatchTimeoutSeconds
        }, setting: ${JSON.stringify(settingStore.$state)} `
      );
    } else {
      loggerRenderer.error(`It's not an integer or not between 3 and 60. (${numTemp})`);
    }
  }
);

const arrTimeoutRules = [
  (v: string) => {
    const numValue = parseFloat(v);
    return Number.isInteger(numValue) || "Value must be an integer.";
  },
  (v: string) => {
    const numValue = parseFloat(v);
    return numValue >= 3 || "Value must be at least 3.";
  },
  (v: string) => {
    const numValue = parseFloat(v);
    return numValue <= 60 || "Value must be no more than 60.";
  },
];

watch(
  () => intIndicateDelay.value,
  (newValue) => {
    // In fact, type of newValue is string. But static check thinks it is number, use toString().
    const numTemp = parseFloat(newValue.toString());

    if (Number.isInteger(numTemp) && numTemp >= 1 && numTemp <= 10) {
      settingStore.intIndicateDelaySeconds = numTemp;
      loggerRenderer.debug(
        `Modify setting: settingStore.intIndicateDelaySeconds = ${
          settingStore.intIndicateDelaySeconds
        }, setting: ${JSON.stringify(settingStore.$state)} `
      );
    } else {
      loggerRenderer.error(`It's not an integer or not between 1 and 10. (${numTemp})`);
    }
  }
);

const arrDelayRules = [
  (v: string) => {
    const numValue = parseFloat(v);
    return Number.isInteger(numValue) || "Value must be an integer.";
  },
  (v: string) => {
    const numValue = parseFloat(v);
    return numValue >= 1 || "Value must be at least 1.";
  },
  (v: string) => {
    const numValue = parseFloat(v);
    return numValue <= 10 || "Value must be no more than 10.";
  },
];

watch(
  () => floatConfidence.value,
  (newValue) => {
    // In fact, type of newValue is string. But static check thinks it is number, use toString().
    const numTemp = parseFloat(newValue.toString());

    if (numTemp >= 0.1 && numTemp <= 0.999) {
      settingStore.confidence = numTemp;
      loggerRenderer.debug(
        `Modify setting: settingStore.confidence = ${
          settingStore.confidence
        }, setting: ${JSON.stringify(settingStore.$state)} `
      );
    } else {
      loggerRenderer.error(`It's not a float between 0.1 and 0.999. (${numTemp})`);
    }
  }
);

const arrConfidence = [
  (v: string) => {
    const numValue = parseFloat(v);
    return numValue >= 0.1 || "Value must be at least 0.1";
  },
  (v: string) => {
    const numValue = parseFloat(v);
    return numValue <= 0.999 || "Value must be no more than 0.999";
  },
];
</script>

<style scoped></style>
