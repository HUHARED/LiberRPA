<!-- FileName: RetentionSettings.vue -->
<template>
  <v-container fluid class="pa-2 ma-0 flex-row">
    <v-tooltip location="bottom">
      <template #activator="{ props }">
        <v-icon
          class="pa-0 ma-0 mt-2 mr-2"
          color="medium-emphasis"
          icon="mdi-delete-clock-outline"
          v-bind="props">
        </v-icon>
      </template>

      <div>
        Delete run log folders older than the configured retention period, including logs
        and videos.<br />
        Minimum: 7 days.<br />
        Checked when Executor starts and every hour while it is running.<br />
        Changes take effect only after you click Apply.
      </div>
    </v-tooltip>

    <v-checkbox
      v-model="boolLogTimeoutEnable"
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
      :disabled="!boolLogTimeoutEnable">
    </v-number-input>

    <span class="pa-0 ma-0 mt-2">days</span>
  </v-container>

  <v-container fluid class="pa-2 ma-0 flex-row">
    <v-tooltip location="bottom">
      <template #activator="{ props }">
        <v-icon
          class="pa-0 ma-0 mt-2 mr-2"
          color="medium-emphasis"
          icon="mdi-video-off-outline"
          v-bind="props">
        </v-icon>
      </template>

      <div>
        Delete run videos older than the configured retention period.<br />
        Minimum: 1 day.<br />
        Checked when Executor starts and every hour while it is running.<br />
        Changes take effect only after you click Apply.
      </div>
    </v-tooltip>

    <v-checkbox
      v-model="boolVideoTimeoutEnable"
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
      :disabled="!boolVideoTimeoutEnable">
    </v-number-input>

    <span class="pa-0 ma-0 mt-2">days</span>
  </v-container>

  <v-container fluid class="pa-2 ma-0 flex-row">
    <v-tooltip location="bottom">
      <template #activator="{ props }">
        <v-icon
          class="pa-0 ma-0 mt-2 mr-2"
          color="medium-emphasis"
          icon="mdi-video-minus-outline"
          v-bind="props">
        </v-icon>
      </template>

      <div>
        Delete the oldest run videos when total video storage exceeds this limit.<br />
        Minimum: 1 GB.<br />
        Checked when Executor starts and every hour while it is running.<br />
        Changes take effect only after you click Apply.
      </div>
    </v-tooltip>

    <v-checkbox
      v-model="boolVideoSizeEnable"
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
      :disabled="!boolVideoSizeEnable">
    </v-number-input>

    <span class="pa-0 ma-0 mt-2">GB</span>

    <v-btn
      class="ml-4"
      size="small"
      variant="text"
      :disabled="!boolHasChanges"
      @click="resetRetentionDraft()">
      Cancel
    </v-btn>

    <v-btn
      class="ml-2"
      size="small"
      color="primary"
      variant="tonal"
      :disabled="!boolHasChanges"
      @click="applyRetentionSettings()">
      Apply
    </v-btn>
  </v-container>

  <v-dialog v-model="boolConfirmationDialogOpen" max-width="520">
    <v-card title="Apply Retention Settings?">
      <v-card-text>
        Applying these settings may permanently delete existing Run logs or videos during
        the next cleanup. This operation cannot be undone.
      </v-card-text>

      <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn variant="text" @click="boolConfirmationDialogOpen = false"> Cancel </v-btn>
        <v-btn color="warning" variant="tonal" @click="confirmRetentionSettings()">
          Apply
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { useInformationStore } from "../../Store/informationStore";
import { useSettingStore } from "../../Store/settingStore";

interface RetentionValues {
  logTimeoutEnable: boolean;
  logTimeoutDays: number;
  videoTimeoutEnable: boolean;
  videoTimeoutDays: number;
  videoSizeEnable: boolean;
  videoSizeGB: number;
}

const informationStore = useInformationStore();
const settingStore = useSettingStore();

const boolLogTimeoutEnable = ref(false);
const intLogTimeoutDays = ref<number | null>(7);
const boolVideoTimeoutEnable = ref(false);
const intVideoTimeoutDays = ref<number | null>(1);
const boolVideoSizeEnable = ref(false);
const intVideoSizeGB = ref<number | null>(1);
const boolConfirmationDialogOpen = ref(false);

const boolHasChanges = computed(
  () =>
    boolLogTimeoutEnable.value !== settingStore.logTimeoutEnable ||
    intLogTimeoutDays.value !== settingStore.logTimeoutDays ||
    boolVideoTimeoutEnable.value !== settingStore.videoTimeoutEnable ||
    intVideoTimeoutDays.value !== settingStore.videoTimeoutDays ||
    boolVideoSizeEnable.value !== settingStore.videoSizeEnable ||
    intVideoSizeGB.value !== settingStore.videoSizeGB,
);

watch(
  () =>
    [
      settingStore.logTimeoutEnable,
      settingStore.logTimeoutDays,
      settingStore.videoTimeoutEnable,
      settingStore.videoTimeoutDays,
      settingStore.videoSizeEnable,
      settingStore.videoSizeGB,
    ] as const,
  () => {
    resetRetentionDraft();
  },
  { immediate: true },
);

function resetRetentionDraft(): void {
  boolLogTimeoutEnable.value = settingStore.logTimeoutEnable;
  intLogTimeoutDays.value = settingStore.logTimeoutDays;
  boolVideoTimeoutEnable.value = settingStore.videoTimeoutEnable;
  intVideoTimeoutDays.value = settingStore.videoTimeoutDays;
  boolVideoSizeEnable.value = settingStore.videoSizeEnable;
  intVideoSizeGB.value = settingStore.videoSizeGB;
  boolConfirmationDialogOpen.value = false;
}

function getRetentionValues(): RetentionValues | undefined {
  const intLogTimeoutDaysValue = intLogTimeoutDays.value;
  if (
    intLogTimeoutDaysValue === null ||
    !Number.isSafeInteger(intLogTimeoutDaysValue) ||
    intLogTimeoutDaysValue < 7
  ) {
    informationStore.showAlertMessage(
      `Run Log Retention must be an integer >= 7. (${String(intLogTimeoutDaysValue)})`,
    );
    return undefined;
  }

  const intVideoTimeoutDaysValue = intVideoTimeoutDays.value;
  if (
    intVideoTimeoutDaysValue === null ||
    !Number.isSafeInteger(intVideoTimeoutDaysValue) ||
    intVideoTimeoutDaysValue < 1
  ) {
    informationStore.showAlertMessage(
      `Video Retention must be an integer >= 1. (${String(intVideoTimeoutDaysValue)})`,
    );
    return undefined;
  }

  const intVideoSizeGBValue = intVideoSizeGB.value;
  if (
    intVideoSizeGBValue === null ||
    !Number.isSafeInteger(intVideoSizeGBValue) ||
    intVideoSizeGBValue < 1
  ) {
    informationStore.showAlertMessage(
      `Video Storage Limit must be an integer >= 1. (${String(intVideoSizeGBValue)})`,
    );
    return undefined;
  }

  return {
    logTimeoutEnable: boolLogTimeoutEnable.value,
    logTimeoutDays: intLogTimeoutDaysValue,
    videoTimeoutEnable: boolVideoTimeoutEnable.value,
    videoTimeoutDays: intVideoTimeoutDaysValue,
    videoSizeEnable: boolVideoSizeEnable.value,
    videoSizeGB: intVideoSizeGBValue,
  };
}

function mayDeleteMoreFiles(valuesDict: RetentionValues): boolean {
  return (
    (valuesDict.logTimeoutEnable &&
      (!settingStore.logTimeoutEnable ||
        valuesDict.logTimeoutDays < settingStore.logTimeoutDays)) ||
    (valuesDict.videoTimeoutEnable &&
      (!settingStore.videoTimeoutEnable ||
        valuesDict.videoTimeoutDays < settingStore.videoTimeoutDays)) ||
    (valuesDict.videoSizeEnable &&
      (!settingStore.videoSizeEnable || valuesDict.videoSizeGB < settingStore.videoSizeGB))
  );
}

function applyRetentionSettings(): void {
  const dictValues = getRetentionValues();
  if (dictValues === undefined) {
    return;
  }

  if (mayDeleteMoreFiles(dictValues)) {
    boolConfirmationDialogOpen.value = true;
    return;
  }

  saveRetentionSettings(dictValues);
}

function confirmRetentionSettings(): void {
  const dictValues = getRetentionValues();
  if (dictValues === undefined) {
    boolConfirmationDialogOpen.value = false;
    return;
  }

  saveRetentionSettings(dictValues);
}

function saveRetentionSettings(dictValues: RetentionValues): void {
  settingStore.logTimeoutEnable = dictValues.logTimeoutEnable;
  settingStore.logTimeoutDays = dictValues.logTimeoutDays;
  settingStore.videoTimeoutEnable = dictValues.videoTimeoutEnable;
  settingStore.videoTimeoutDays = dictValues.videoTimeoutDays;
  settingStore.videoSizeEnable = dictValues.videoSizeEnable;
  settingStore.videoSizeGB = dictValues.videoSizeGB;
  boolConfirmationDialogOpen.value = false;
}
</script>

<style scoped></style>
