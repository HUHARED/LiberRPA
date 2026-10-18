<!-- FileName: BuiltInArguments.vue -->
<template>
  <v-row>
    <v-col cols="12" sm="7">
      <slot name="environment" />
    </v-col>

    <v-col cols="12" sm="5">
      <v-number-input
        v-model="settings.max_retry_count"
        :control-variant="readonly ? 'hidden' : 'default'"
        :variant="readonly ? 'plain' : 'underlined'"
        density="compact"
        :error-messages="getFieldErrors(fieldErrors, 'settings.max_retry_count')"
        label="Max Retry Count"
        :min="0"
        :max="INT_MAX_RETRY_COUNT"
        :precision="0"
        :rules="[validateMaxRetryCount]"
        :disabled="disabled"
        :readonly="readonly"
        hide-details="auto">
        <v-tooltip activator="parent" location="top">
          Maximum extra attempts after an execution error.
        </v-tooltip>
      </v-number-input>
    </v-col>
  </v-row>

  <v-row class="mt-1">
    <v-col cols="12" sm="7">
      <v-number-input
        v-model="settings.timeout_min"
        :control-variant="readonly ? 'hidden' : 'default'"
        :variant="readonly ? 'plain' : 'underlined'"
        density="compact"
        :error-messages="getFieldErrors(fieldErrors, 'settings.timeout_min')"
        label="Timeout (min)"
        :min="0"
        :max="INT_MAX_TIMEOUT_MIN"
        :precision="0"
        :rules="[validateTimeout]"
        :disabled="disabled"
        :readonly="readonly"
        hide-details="auto">
        <v-tooltip activator="parent" location="top">
          Stop the run when it exceeds this timeout. 0 means no limit. Maximum:
          {{ INT_MAX_TIMEOUT_MIN }} minutes. Applies to each attempt.
        </v-tooltip>
      </v-number-input>
    </v-col>

    <v-col cols="12" sm="5">
      <v-select
        v-model="settings.builtin_log_level"
        :variant="readonly ? 'plain' : 'underlined'"
        :menu-icon="readonly ? '' : undefined"
        density="compact"
        :error-messages="getFieldErrors(fieldErrors, 'settings.builtin_log_level')"
        label="Log Level"
        :items="ARR_LOG_LEVEL"
        :disabled="disabled"
        :readonly="readonly" />
    </v-col>
  </v-row>

  <v-switch
    v-model="settings.builtin_record_video"
    :error-messages="getFieldErrors(fieldErrors, 'settings.builtin_record_video')"
    label="Record Video"
    true-icon="mdi-video-outline"
    hide-details="auto"
    :disabled="disabled"
    :readonly="readonly" />

  <v-switch
    v-model="settings.builtin_stop_shortcut"
    :error-messages="getFieldErrors(fieldErrors, 'settings.builtin_stop_shortcut')"
    label="Stop Shortcut"
    true-icon="mdi-stop-circle-outline"
    hide-details="auto"
    :disabled="disabled"
    :readonly="readonly" />

  <v-switch
    v-model="settings.builtin_highlight_ui"
    :error-messages="getFieldErrors(fieldErrors, 'settings.builtin_highlight_ui')"
    label="Highlight UI"
    true-icon="mdi-rectangle-outline"
    hide-details="auto"
    :disabled="disabled"
    :readonly="readonly" />
</template>

<script setup lang="ts">
import { getFieldErrors } from "@/api/errors";
import {
  type RunSettings,
  ARR_LOG_LEVEL,
  INT_MAX_RETRY_COUNT,
  INT_MAX_TIMEOUT_MIN,
} from "@/api/runSettings";

defineProps<{
  disabled?: boolean;
  readonly?: boolean;
  fieldErrors?: Record<string, string[]>;
}>();

const settings = defineModel<RunSettings>({ required: true });

function validateMaxRetryCount(value: unknown): true | string {
  return (
    (typeof value === "number" &&
      Number.isInteger(value) &&
      value >= 0 &&
      value <= INT_MAX_RETRY_COUNT) ||
    `Enter an integer from 0 to ${INT_MAX_RETRY_COUNT}.`
  );
}

function validateTimeout(value: unknown): true | string {
  return (
    (typeof value === "number" &&
      Number.isInteger(value) &&
      value >= 0 &&
      value <= INT_MAX_TIMEOUT_MIN) ||
    `Enter an integer from 0 to ${INT_MAX_TIMEOUT_MIN}.`
  );
}
</script>

<style scoped></style>
