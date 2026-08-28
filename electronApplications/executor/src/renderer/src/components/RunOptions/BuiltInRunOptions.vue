<!-- FileName: BuiltInRunOptions.vue -->
<template>
  <v-row class="w-100">
    <v-col :cols="props.timeoutCols">
      <v-number-input
        v-model="intTimeoutMin"
        control-variant="default"
        label="Timeout (min)"
        :min="0"
        :max="INT_MAX_RUN_TIMEOUT_MIN"
        :precision="0"
        inset
        density="compact"
        variant="underlined"
        hide-details>
        <v-tooltip activator="parent" location="top">
          Stop the run when it exceeds this timeout. 0 means no limit.
        </v-tooltip>
      </v-number-input>
    </v-col>

    <v-col :cols="props.logLevelCols">
      <v-select
        v-model="logLevel"
        label="Log Level"
        variant="underlined"
        class="clean-space"
        density="compact"
        hide-details
        :items="ARR_LOG_LEVEL">
      </v-select>
    </v-col>
  </v-row>

  <v-container fluid class="clean-space flex-column mt-2">
    <v-label class="clean-space" style="font-size: 0.75em"> Record Video </v-label>

    <v-switch
      v-model="recordVideo"
      hide-details
      class="clean-space pl-1"
      density="compact"
      true-icon="mdi-video-outline">
    </v-switch>

    <v-label class="clean-space" style="font-size: 0.75em"> Stop Shortcut </v-label>

    <v-switch
      v-model="stopShortcut"
      hide-details
      class="clean-space pl-1"
      density="compact"
      true-icon="mdi-stop-circle-outline">
    </v-switch>

    <v-label class="clean-space" style="font-size: 0.75em"> Highlight UI </v-label>

    <v-switch
      v-model="highlightUi"
      hide-details
      class="clean-space pl-1"
      density="compact"
      true-icon="mdi-rectangle-outline">
    </v-switch>
  </v-container>
</template>

<script setup lang="ts">
import { computed } from "vue";

import { ARR_LOG_LEVEL } from "../../RunOptions/runOptions";
import { useInformationStore } from "../../Store/informationStore";
import { INT_MAX_RUN_TIMEOUT_MIN } from "../../../../shared/runOptions";
import type { Str_LogLevel } from "../../../../shared/runOptions";

const props = withDefaults(
  defineProps<{
    timeoutCols?: number;
    logLevelCols?: number;
  }>(),
  {
    timeoutCols: 6,
    logLevelCols: 6,
  },
);

const timeoutMin = defineModel<number>("timeoutMin", { required: true });
const logLevel = defineModel<Str_LogLevel>("logLevel", { required: true });
const recordVideo = defineModel<boolean>("recordVideo", { required: true });
const stopShortcut = defineModel<boolean>("stopShortcut", { required: true });
const highlightUi = defineModel<boolean>("highlightUi", { required: true });

const informationStore = useInformationStore();

const intTimeoutMin = computed<number>({
  get() {
    return timeoutMin.value;
  },
  set(newValue: number | null) {
    if (
      newValue === null ||
      !Number.isSafeInteger(newValue) ||
      newValue < 0 ||
      newValue > INT_MAX_RUN_TIMEOUT_MIN
    ) {
      informationStore.showAlertMessage(
        `Timeout must be an integer from 0 to ${String(INT_MAX_RUN_TIMEOUT_MIN)}. (${String(newValue)})`,
      );
      return;
    }

    timeoutMin.value = newValue;
  },
});
</script>

<style scoped></style>
