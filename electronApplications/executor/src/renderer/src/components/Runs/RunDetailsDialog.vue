<!-- FileName: RunDetailsDialog.vue -->
<template>
  <v-dialog
    :model-value="true"
    max-width="850"
    height="80vh"
    scrollable
    @update:model-value="!$event && emit('close')">
    <v-card title="Run Details" class="overflow-hidden">
      <v-card-subtitle class="flex-shrink-0 px-6 pb-3 text-wrap">
        {{ sourceLabel }} · Attempt {{ details.attempt_number }}
        <span v-if="details.source === RunSource.Console" class="d-block text-break">
          Job {{ details.job_id }}
        </span>
      </v-card-subtitle>

      <v-card-text class="d-flex flex-column flex-1-1-0 ga-4 overflow-hidden">
        <v-card variant="flat" border class="d-flex flex-column flex-1-1-0 overflow-hidden">
          <v-card-title
            tag="h3"
            class="text-subtitle-1 font-weight-bold flex-shrink-0 py-2">
            Inputs
          </v-card-title>

          <v-card-subtitle class="flex-shrink-0 pb-2 text-wrap">
            Run settings and initial CustomArgs.
          </v-card-subtitle>

          <v-divider />

          <v-card-text
            class="flex-1-1-0 overflow-y-auto pa-3"
            role="region"
            aria-label="Inputs"
            tabindex="0">
            <pre class="text-pre-wrap text-break"><code><span
              v-for="(token, index) in arrInputsToken"
              :key="index"
              :class="typeof token === 'string' ? undefined : DICT_TOKEN_COLOR[token.type]"
              v-text="typeof token === 'string' ? token : token.content" /></code></pre>
          </v-card-text>
        </v-card>

        <v-card variant="flat" border class="d-flex flex-column flex-1-1-0 overflow-hidden">
          <v-card-title
            tag="h3"
            class="text-subtitle-1 font-weight-bold flex-shrink-0 py-2">
            Outputs — {{ details.outputs.status }}
          </v-card-title>

          <v-card-subtitle class="flex-shrink-0 pb-2 text-wrap">
            Final CustomArgs from the main process.
          </v-card-subtitle>

          <v-divider />

          <v-card-text
            class="flex-1-1-0 overflow-y-auto pa-3"
            role="region"
            aria-label="Outputs"
            tabindex="0">
            <v-alert v-if="details.outputs.reason" variant="tonal" class="mb-3">
              {{ details.outputs.reason }}
            </v-alert>

            <pre class="text-pre-wrap text-break"><code><span
              v-for="(token, index) in arrOutputsToken"
              :key="index"
              :class="typeof token === 'string' ? undefined : DICT_TOKEN_COLOR[token.type]"
              v-text="typeof token === 'string' ? token : token.content" /></code></pre>

            <p v-if="details.outputs.unavailableKeys.length" class="text-break mt-3">
              Unavailable: {{ details.outputs.unavailableKeys.join(", ") }}
            </p>

            <v-alert v-if="details.error_summary" type="error" variant="tonal" class="mt-3">
              {{ details.error_summary.type }}: {{ details.error_summary.message }}
            </v-alert>
          </v-card-text>
        </v-card>
      </v-card-text>

      <v-card-actions>
        <v-btn variant="tonal" prepend-icon="mdi-close" @click="emit('close')">Close</v-btn>
        <v-spacer />
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed } from "vue";
import Prism from "prismjs/components/prism-core";
import "prismjs/components/prism-json";

import { RunSource, type RunDetails } from "../../../../shared/run";

const props = defineProps<{ details: RunDetails; sourceLabel: string }>();
const emit = defineEmits<{ close: [] }>();

Prism.manual = true;

const DICT_TOKEN_COLOR: Record<string, string> = {
  property: "text-primary",
  string: "text-success",
  number: "text-warning",
  boolean: "text-warning",
  null: "text-warning",
};

const arrInputsToken = computed(() =>
  Prism.tokenize(JSON.stringify(props.details.snapshot, null, 2), Prism.languages.json),
);

const arrOutputsToken = computed(() =>
  Prism.tokenize(
    JSON.stringify(props.details.outputs.values, null, 2),
    Prism.languages.json,
  ),
);
</script>

<style scoped></style>
