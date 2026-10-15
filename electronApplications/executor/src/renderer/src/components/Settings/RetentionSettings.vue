<!-- FileName: RetentionSettings.vue -->
<template>
  <v-container fluid class="pa-2 ma-0 flex-row">
    <v-tooltip location="bottom">
      <template #activator="{ props }">
        <v-icon
          class="pa-0 ma-0 mt-2 mr-2"
          color="medium-emphasis"
          icon="mdi-delete-clock-outline"
          v-bind="props"></v-icon>
      </template>

      <div>
        Delete run log folders older than the configured retention period, including logs
        and videos.
        <br />
        Minimum: 7 days.
        <br />
        Checked when Executor starts and every hour while it is running.
        <br />
        Changes take effect only after you click Apply.
      </div>
    </v-tooltip>

    <v-checkbox
      v-model="boolLogRetentionEnabled"
      class="clean-space"
      density="compact"
      label="Run Log Retention"
      hide-details></v-checkbox>

    <v-number-input
      v-model="intLogRetentionDays"
      class="pa-0 ma-0 ml-2"
      density="compact"
      hide-details
      control-variant="stacked"
      inset
      :min="7"
      :precision="0"
      style="max-width: 100px"
      :disabled="!boolLogRetentionEnabled"></v-number-input>

    <span class="pa-0 ma-0 mt-2">days</span>
  </v-container>

  <v-container fluid class="pa-2 ma-0 flex-row">
    <v-tooltip location="bottom">
      <template #activator="{ props }">
        <v-icon
          class="pa-0 ma-0 mt-2 mr-2"
          color="medium-emphasis"
          icon="mdi-video-off-outline"
          v-bind="props"></v-icon>
      </template>

      <div>
        Delete run videos older than the configured retention period.
        <br />
        Minimum: 1 day.
        <br />
        Checked when Executor starts and every hour while it is running.
        <br />
        Changes take effect only after you click Apply.
      </div>
    </v-tooltip>

    <v-checkbox
      v-model="boolVideoRetentionEnabled"
      class="clean-space"
      density="compact"
      label="Video Retention"
      hide-details></v-checkbox>

    <v-number-input
      v-model="intVideoRetentionDays"
      class="pa-0 ma-0 ml-2"
      density="compact"
      hide-details
      control-variant="stacked"
      inset
      :min="1"
      :precision="0"
      style="max-width: 100px"
      :disabled="!boolVideoRetentionEnabled"></v-number-input>

    <span class="pa-0 ma-0 mt-2">days</span>
  </v-container>

  <v-container fluid class="pa-2 ma-0 flex-row">
    <v-tooltip location="bottom">
      <template #activator="{ props }">
        <v-icon
          class="pa-0 ma-0 mt-2 mr-2"
          color="medium-emphasis"
          icon="mdi-video-minus-outline"
          v-bind="props"></v-icon>
      </template>

      <div>
        Delete the oldest run videos when total video storage exceeds this limit.
        <br />
        Minimum: 1 GiB.
        <br />
        Checked when Executor starts and every hour while it is running.
        <br />
        Changes take effect only after you click Apply.
      </div>
    </v-tooltip>

    <v-checkbox
      v-model="boolVideoStorageLimitEnabled"
      class="clean-space"
      density="compact"
      label="Video Storage Limit"
      hide-details></v-checkbox>

    <v-number-input
      v-model="intVideoStorageLimitGiB"
      class="pa-0 ma-0 ml-2"
      density="compact"
      hide-details
      control-variant="stacked"
      inset
      :min="1"
      :precision="0"
      style="max-width: 100px"
      :disabled="!boolVideoStorageLimitEnabled"></v-number-input>

    <span class="pa-0 ma-0 mt-2">GiB</span>

    <v-btn
      class="ml-4"
      size="small"
      variant="tonal"
      prepend-icon="mdi-close"
      :disabled="!boolHasChanges"
      @click="resetRetentionDraft()">
      Cancel
    </v-btn>

    <v-btn
      class="ml-2"
      size="small"
      color="primary"
      variant="tonal"
      prepend-icon="mdi-check"
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
        <v-btn variant="tonal" @click="boolConfirmationDialogOpen = false">Cancel</v-btn>
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
  logRetentionEnabled: boolean;
  logRetentionDays: number;
  videoRetentionEnabled: boolean;
  videoRetentionDays: number;
  videoStorageLimitEnabled: boolean;
  videoStorageLimitGiB: number;
}

const informationStore = useInformationStore();
const settingStore = useSettingStore();

const boolLogRetentionEnabled = ref(false);
const intLogRetentionDays = ref<number | null>(7);
const boolVideoRetentionEnabled = ref(false);
const intVideoRetentionDays = ref<number | null>(1);
const boolVideoStorageLimitEnabled = ref(false);
const intVideoStorageLimitGiB = ref<number | null>(1);
const boolConfirmationDialogOpen = ref(false);

const boolHasChanges = computed(
  () =>
    boolLogRetentionEnabled.value !== settingStore.logRetentionEnabled ||
    intLogRetentionDays.value !== settingStore.logRetentionDays ||
    boolVideoRetentionEnabled.value !== settingStore.videoRetentionEnabled ||
    intVideoRetentionDays.value !== settingStore.videoRetentionDays ||
    boolVideoStorageLimitEnabled.value !== settingStore.videoStorageLimitEnabled ||
    intVideoStorageLimitGiB.value !== settingStore.videoStorageLimitGiB,
);

watch(
  () =>
    [
      settingStore.logRetentionEnabled,
      settingStore.logRetentionDays,
      settingStore.videoRetentionEnabled,
      settingStore.videoRetentionDays,
      settingStore.videoStorageLimitEnabled,
      settingStore.videoStorageLimitGiB,
    ] as const,
  () => {
    resetRetentionDraft();
  },
  { immediate: true },
);

function resetRetentionDraft(): void {
  boolLogRetentionEnabled.value = settingStore.logRetentionEnabled;
  intLogRetentionDays.value = settingStore.logRetentionDays;
  boolVideoRetentionEnabled.value = settingStore.videoRetentionEnabled;
  intVideoRetentionDays.value = settingStore.videoRetentionDays;
  boolVideoStorageLimitEnabled.value = settingStore.videoStorageLimitEnabled;
  intVideoStorageLimitGiB.value = settingStore.videoStorageLimitGiB;
  boolConfirmationDialogOpen.value = false;
}

function getRetentionValues(): RetentionValues | undefined {
  const intLogRetentionDaysValue = intLogRetentionDays.value;
  if (
    intLogRetentionDaysValue === null ||
    !Number.isSafeInteger(intLogRetentionDaysValue) ||
    intLogRetentionDaysValue < 7
  ) {
    informationStore.showAlertMessage(
      `Run Log Retention must be an integer >= 7. (${String(intLogRetentionDaysValue)})`,
    );
    return undefined;
  }

  const intVideoRetentionDaysValue = intVideoRetentionDays.value;
  if (
    intVideoRetentionDaysValue === null ||
    !Number.isSafeInteger(intVideoRetentionDaysValue) ||
    intVideoRetentionDaysValue < 1
  ) {
    informationStore.showAlertMessage(
      `Video Retention must be an integer >= 1. (${String(intVideoRetentionDaysValue)})`,
    );
    return undefined;
  }

  const intVideoStorageLimitGiBValue = intVideoStorageLimitGiB.value;
  if (
    intVideoStorageLimitGiBValue === null ||
    !Number.isSafeInteger(intVideoStorageLimitGiBValue) ||
    intVideoStorageLimitGiBValue < 1
  ) {
    informationStore.showAlertMessage(
      `Video Storage Limit must be an integer >= 1. (${String(intVideoStorageLimitGiBValue)})`,
    );
    return undefined;
  }

  return {
    logRetentionEnabled: boolLogRetentionEnabled.value,
    logRetentionDays: intLogRetentionDaysValue,
    videoRetentionEnabled: boolVideoRetentionEnabled.value,
    videoRetentionDays: intVideoRetentionDaysValue,
    videoStorageLimitEnabled: boolVideoStorageLimitEnabled.value,
    videoStorageLimitGiB: intVideoStorageLimitGiBValue,
  };
}

function mayDeleteMoreFiles(valuesDict: RetentionValues): boolean {
  return (
    (valuesDict.logRetentionEnabled &&
      (!settingStore.logRetentionEnabled ||
        valuesDict.logRetentionDays < settingStore.logRetentionDays)) ||
    (valuesDict.videoRetentionEnabled &&
      (!settingStore.videoRetentionEnabled ||
        valuesDict.videoRetentionDays < settingStore.videoRetentionDays)) ||
    (valuesDict.videoStorageLimitEnabled &&
      (!settingStore.videoStorageLimitEnabled ||
        valuesDict.videoStorageLimitGiB < settingStore.videoStorageLimitGiB))
  );
}

function saveRetentionSettings(dictValues: RetentionValues): void {
  settingStore.logRetentionEnabled = dictValues.logRetentionEnabled;
  settingStore.logRetentionDays = dictValues.logRetentionDays;
  settingStore.videoRetentionEnabled = dictValues.videoRetentionEnabled;
  settingStore.videoRetentionDays = dictValues.videoRetentionDays;
  settingStore.videoStorageLimitEnabled = dictValues.videoStorageLimitEnabled;
  settingStore.videoStorageLimitGiB = dictValues.videoStorageLimitGiB;
  boolConfirmationDialogOpen.value = false;
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
</script>

<style scoped></style>
