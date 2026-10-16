<!-- FileName: RunTable.vue -->
<template>
  <v-table>
    <thead>
      <tr>
        <th>Attempt</th>
        <th>Executor</th>
        <th>Started At</th>
        <th>Ended At</th>
        <th>Status</th>
        <th>Actions</th>
      </tr>
    </thead>

    <tbody>
      <tr v-for="run in runs" :key="run.id">
        <td>{{ run.attempt_number }}</td>
        <td>{{ run.executor_name }}</td>
        <td class="text-no-wrap">{{ formatDateTime(run.started_at, timeZone) }}</td>
        <td class="text-no-wrap">
          {{ formatRunEndTime(run, timeZone) }}
        </td>
        <td>
          <v-chip
            :border="`${RUN_STATUS_COLORS[run.status]} thin opacity-25`"
            :color="RUN_STATUS_COLORS[run.status]"
            :text="RUN_STATUS_LABELS[run.status]"
            variant="text"
            size="x-small" />
        </td>
        <td>
          <v-btn
            v-tooltip:bottom="'View Run Details'"
            :to="{ name: 'run-details', params: { runId: run.id } }"
            size="small"
            variant="text"
            aria-label="View Run Details"
            icon="mdi-eye-outline" />
        </td>
      </tr>

      <tr v-if="!runs.length">
        <td colspan="6">{{ emptyText ?? "No runs." }}</td>
      </tr>
    </tbody>
  </v-table>
</template>

<script setup lang="ts">
import type { RunInfo } from "@/api/runs";
import { RUN_STATUS_LABELS, RUN_STATUS_COLORS } from "@/app/runLabels";
import { formatDateTime, formatRunEndTime } from "@/app/formatters";

defineProps<{
  runs: RunInfo[];
  timeZone: string;
  emptyText?: string;
}>();
</script>

<style scoped></style>
