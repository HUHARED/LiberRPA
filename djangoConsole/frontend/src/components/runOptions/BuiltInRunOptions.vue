<!-- FileName: BuiltInRunOptions.vue -->
<template>
  <v-row>
    <v-col v-if="$slots.environment" cols="12" sm="6">
      <slot name="environment" />
    </v-col>
    <v-col cols="12" :sm="$slots.environment ? 6 : 12">
      <v-number-input
        v-model="settings.max_retry_count"
        :control-variant="readonly ? 'hidden' : 'default'"
        variant="underlined"
        density="compact"
        :error-messages="getFieldErrors(fieldErrors, 'settings.max_retry_count')"
        label="Max Retry Count"
        :min="0"
        :max="3"
        :precision="0"
        :rules="[validateMaxRetryCount]"
        :disabled="disabled"
        :readonly="readonly"
        hint="Maximum extra attempts after an execution error."
        persistent-hint />
    </v-col>
  </v-row>
  <v-row class="mt-1">
    <v-col cols="12" sm="7">
      <v-number-input
        v-model="settings.timeout_min"
        :control-variant="readonly ? 'hidden' : 'default'"
        variant="underlined"
        density="compact"
        :error-messages="getFieldErrors(fieldErrors, 'settings.timeout_min')"
        label="Timeout (min)"
        :min="0"
        :max="INT_MAX_TIMEOUT_MIN"
        :precision="0"
        :rules="[validateTimeout]"
        :disabled="disabled"
        :readonly="readonly"
        hint="0 means no limit. Applies to each attempt."
        persistent-hint />
    </v-col>
    <v-col cols="12" sm="5">
      <v-select
        v-model="settings.builtin_log_level"
        :menu-icon="readonly ? '' : undefined"
        variant="underlined"
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
import { type RunSettings, ARR_LOG_LEVEL, INT_MAX_TIMEOUT_MIN } from "@/api/runOptions";

defineProps<{
  disabled?: boolean;
  readonly?: boolean;
  fieldErrors?: Record<string, string[]>;
}>();
const settings = defineModel<RunSettings>({ required: true });

function validateMaxRetryCount(value: unknown): true | string {
  return (
    (typeof value === "number" && Number.isInteger(value) && value >= 0 && value <= 3) ||
    "Enter an integer from 0 to 3."
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
