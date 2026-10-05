<!-- FileName: RunInputs.vue -->
<template>
  <v-table density="compact">
    <thead>
      <tr>
        <th>Field</th>
        <th>Value</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Python Environment</td>
        <td>{{ inputs.python_environment_name }}</td>
      </tr>
      <tr>
        <td>Retry Count</td>
        <td>{{ inputs.retry_count }}</td>
      </tr>
      <tr>
        <td>Timeout</td>
        <td>{{ inputs.timeout_min === 0 ? "No limit" : `${inputs.timeout_min} min` }}</td>
      </tr>
      <tr>
        <td>Log Level</td>
        <td>{{ inputs.builtin_log_level }}</td>
      </tr>
      <tr>
        <td>Record Video</td>
        <td>{{ inputs.builtin_record_video ? "Enabled" : "Disabled" }}</td>
      </tr>
      <tr>
        <td>Stop Shortcut</td>
        <td>{{ inputs.builtin_stop_shortcut ? "Enabled" : "Disabled" }}</td>
      </tr>
      <tr>
        <td>Highlight UI</td>
        <td>{{ inputs.builtin_highlight_ui ? "Enabled" : "Disabled" }}</td>
      </tr>
    </tbody>
  </v-table>
  <h3 class="text-subtitle-1 my-4">Custom Arguments</h3>
  <v-alert v-if="boolDuplicate" type="warning" variant="tonal" class="mb-3">
    Duplicate keys exist. The last value with the same key takes effect.
  </v-alert>
  <p v-if="!inputs.custom_prj_args.length">No custom arguments.</p>
  <v-table v-else>
    <thead>
      <tr>
        <th>Key</th>
        <th>Value</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="(argument, index) in inputs.custom_prj_args" :key="index">
        <td>{{ argument[0] }}</td>
        <td>
          <pre class="text-pre-wrap py-2">{{ formatJsonValue(argument[1]) }}</pre>
        </td>
      </tr>
    </tbody>
  </v-table>
</template>
<script setup lang="ts">
import { computed } from "vue";
import { formatJsonValue, type RunSnapshot } from "@/api/runOptions";
const props = defineProps<{ inputs: RunSnapshot }>();
const boolDuplicate = computed(
  () =>
    new Set(props.inputs.custom_prj_args.map((entry) => entry[0])).size !==
    props.inputs.custom_prj_args.length,
);
</script>
<style scoped></style>
