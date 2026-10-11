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
          {{ run.ended_at ? formatDateTime(run.ended_at, timeZone) : "Unknown" }}
        </td>
        <td>{{ RUN_RESULT_LABELS[run.result] }}</td>
        <td>
          <v-btn
            :to="{ name: 'run-details', params: { runId: run.id } }"
            size="small"
            variant="text">
            View
          </v-btn>
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
import { RUN_RESULT_LABELS } from "@/app/runLabels";
import { formatDateTime } from "@/app/formatters";
defineProps<{
  runs: RunInfo[];
  timeZone: string;
  emptyText?: string;
}>();
</script>
<style scoped></style>
