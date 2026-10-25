<!-- FileName: RunArgumentsDetails.vue -->
<template>
  <v-row>
    <v-col cols="12" md="6">
      <h3 class="text-subtitle-1 mb-3">Built-in Arguments</h3>

      <BuiltInArguments :model-value="settings" readonly>
        <template #environment>
          <v-text-field
            :model-value="pythonEnvironmentName"
            label="Python Environment"
            variant="plain"
            density="compact"
            readonly>
            <v-tooltip activator="parent" location="top">
              {{
                snapshot
                  ? "Python environment captured for this execution. Change Package Settings for future runs."
                  : "Python environment from Package Settings. Change it there for future runs."
              }}
            </v-tooltip>
          </v-text-field>
        </template>
      </BuiltInArguments>
    </v-col>

    <v-col cols="12" md="6">
      <h3 class="text-subtitle-1 mb-3">Custom Project Arguments</h3>

      <v-alert v-if="boolDuplicate" type="warning" variant="tonal" class="mb-3">
        Duplicate keys exist. The last value with the same key takes effect.
      </v-alert>

      <p v-if="!settings.custom_prj_args.length" class="text-medium-emphasis">
        No custom arguments.
      </p>

      <v-row
        v-for="(argument, index) in settings.custom_prj_args"
        :key="index"
        no-gutters
        align="start">
        <v-col cols="5" class="py-1">
          <v-textarea
            :model-value="argument[0]"
            :aria-label="`Argument ${index + 1} name`"
            variant="plain"
            density="compact"
            rows="1"
            auto-grow
            readonly
            hide-details
            spellcheck="false" />
        </v-col>

        <v-col cols="1" class="pt-3 text-center">=</v-col>

        <v-col cols="6" class="py-1">
          <v-textarea
            :model-value="formatJsonValue(argument[1])"
            :aria-label="`Value for ${argument[0]} (JSON)`"
            variant="plain"
            density="compact"
            rows="1"
            auto-grow
            readonly
            hide-details
            spellcheck="false" />
        </v-col>
      </v-row>
    </v-col>
  </v-row>

  <v-divider class="my-5" />
  <h3 class="text-subtitle-1 mb-3">Run Email</h3>

  <v-textarea
    :model-value="strRecipients"
    label="To"
    variant="plain"
    density="compact"
    rows="1"
    auto-grow
    readonly />

  <v-expansion-panels multiple variant="accordion">
    <v-expansion-panel v-for="event in ARR_EVENT" :key="event.key" :value="event.key">
      <v-expansion-panel-title>
        {{ event.title }}
        <v-chip
          :border="`${settings.run_email[event.key].enabled ? 'success' : 'inactive'} thin opacity-25`"
          :color="settings.run_email[event.key].enabled ? 'success' : 'inactive'"
          :text="settings.run_email[event.key].enabled ? 'Enabled' : 'Disabled'"
          variant="text"
          size="x-small"
          class="ml-3" />
      </v-expansion-panel-title>

      <v-expansion-panel-text>
        <v-textarea
          :model-value="settings.run_email[event.key].subject || 'Default template'"
          label="Subject"
          variant="plain"
          density="compact"
          rows="1"
          auto-grow
          readonly />

        <v-textarea
          :model-value="settings.run_email[event.key].body || 'Default template'"
          label="Body (plain text)"
          variant="plain"
          density="compact"
          rows="1"
          auto-grow
          readonly />
      </v-expansion-panel-text>
    </v-expansion-panel>
  </v-expansion-panels>
</template>

<script setup lang="ts">
import { computed } from "vue";

import BuiltInArguments from "./BuiltInArguments.vue";

import { formatJsonValue } from "@/app/formatters";

import type { RunSettings } from "@/api/runSettings";
import type { RunEmailEventKey } from "@/api/runEmail";
import type { RunEmailRecipientDisplayResponse } from "@/api/generated/browserApi";

const props = defineProps<{
  settings: RunSettings;
  emailRecipients: RunEmailRecipientDisplayResponse[];
  pythonEnvironmentName: string;
  snapshot?: boolean;
}>();

const ARR_EVENT: { key: RunEmailEventKey; title: string }[] = [
  { key: "on_start", title: "On Start" },
  { key: "on_completed", title: "On End (Completed)" },
  { key: "on_error", title: "On End (Error / Timeout)" },
];

const strRecipients = computed(
  () =>
    props.emailRecipients
      .map((recipient) => recipient.email ?? `Deleted recipient (${recipient.id})`)
      .join("\n") || "No recipients selected.",
);

const boolDuplicate = computed(
  () =>
    new Set(props.settings.custom_prj_args.map((entry) => entry[0])).size !==
    props.settings.custom_prj_args.length,
);
</script>

<style scoped></style>
