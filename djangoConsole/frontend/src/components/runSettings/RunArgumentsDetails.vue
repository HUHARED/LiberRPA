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
            variant="underlined"
            density="compact"
            readonly />
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
            variant="underlined"
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
</template>

<script setup lang="ts">
import { computed } from "vue";

import BuiltInArguments from "./BuiltInArguments.vue";

import { formatJsonValue } from "@/app/formatters";

import type { RunSettings } from "@/api/runSettings";

const props = defineProps<{ settings: RunSettings; pythonEnvironmentName: string }>();

const boolDuplicate = computed(
  () =>
    new Set(props.settings.custom_prj_args.map((entry) => entry[0])).size !==
    props.settings.custom_prj_args.length,
);
</script>

<style scoped></style>
