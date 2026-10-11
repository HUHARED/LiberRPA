<!-- FileName: RunSettingsDetails.vue -->
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
        <td>{{ pythonEnvironmentName }}</td>
      </tr>
      <tr>
        <td>Max Retry Count</td>
        <td>{{ settings.max_retry_count }}</td>
      </tr>
      <tr>
        <td>Timeout</td>
        <td>
          {{ settings.timeout_min === 0 ? "No limit" : `${settings.timeout_min} min` }}
        </td>
      </tr>
      <tr>
        <td>Log Level</td>
        <td>{{ settings.builtin_log_level }}</td>
      </tr>
      <tr>
        <td>Record Video</td>
        <td>{{ settings.builtin_record_video ? "Enabled" : "Disabled" }}</td>
      </tr>
      <tr>
        <td>Stop Shortcut</td>
        <td>{{ settings.builtin_stop_shortcut ? "Enabled" : "Disabled" }}</td>
      </tr>
      <tr>
        <td>Highlight UI</td>
        <td>{{ settings.builtin_highlight_ui ? "Enabled" : "Disabled" }}</td>
      </tr>
    </tbody>
  </v-table>
  <h3 class="text-subtitle-1 my-4">Custom Arguments</h3>
  <v-alert v-if="boolDuplicate" type="warning" variant="tonal" class="mb-3">
    Duplicate keys exist. The last value with the same key takes effect.
  </v-alert>
  <p v-if="!settings.custom_prj_args.length">No custom arguments.</p>
  <v-table v-else>
    <thead>
      <tr>
        <th>Key</th>
        <th>Value</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="(argument, index) in settings.custom_prj_args" :key="index">
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
import { formatJsonValue } from "@/app/formatters";
import type { RunSettings } from "@/api/runOptions";
const props = defineProps<{ settings: RunSettings; pythonEnvironmentName: string }>();
const boolDuplicate = computed(
  () =>
    new Set(props.settings.custom_prj_args.map((entry) => entry[0])).size !==
    props.settings.custom_prj_args.length,
);
</script>
<style scoped></style>
