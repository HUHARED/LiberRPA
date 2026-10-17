<!-- FileName: JobDetailsView.vue -->
<template>
  <div class="d-flex align-center ga-2 mb-4">
    <v-btn
      :to="{
        name: 'job-queue',
        query: job?.state === JobState.Finished ? { state: JobState.Finished } : {},
      }"
      variant="tonal"
      prepend-icon="mdi-arrow-left">
      Back to Job Queue
    </v-btn>
    <v-spacer />
    <v-btn variant="tonal" prepend-icon="mdi-refresh" :loading="boolLoading" @click="load">
      Refresh
    </v-btn>
  </div>

  <v-alert v-if="strError" type="error" variant="tonal" class="mb-4">
    {{ strError }}
  </v-alert>

  <template v-if="job">
    <div class="d-flex align-center flex-wrap ga-3 mb-4">
      <h1 class="text-h5">{{ job.project_name }} · {{ job.project_version }}</h1>
      <v-chip
        :border="`${JOB_STATE_COLORS[job.state]} thin opacity-25`"
        :color="JOB_STATE_COLORS[job.state]"
        :text="JOB_STATE_LABELS[job.state]"
        variant="text"
        size="x-small" />
      <v-spacer />
      <JobActions :job="job" @updated="load" @error="strError = $event" />
    </div>

    <v-alert
      v-if="job.reason"
      :type="job.state === JobState.NeedsReview ? 'warning' : 'info'"
      variant="tonal"
      class="mb-4">
      {{ job.reason }}
    </v-alert>

    <v-card variant="outlined" class="mb-4">
      <v-card-title>Job Information</v-card-title>

      <v-card-text>
        <v-table>
          <tbody>
            <tr>
              <th scope="row" class="text-caption text-medium-emphasis">Source</th>
              <td>{{ JOB_SOURCE_LABELS[job.source] }}</td>
            </tr>

            <tr>
              <th scope="row" class="text-caption text-medium-emphasis">Schedule</th>
              <td>{{ job.schedule_name || "—" }}</td>
            </tr>

            <tr>
              <th scope="row" class="text-caption text-medium-emphasis">Scheduled At</th>
              <td>{{ formatDateTime(job.scheduled_at, strTimeZone) }}</td>
            </tr>

            <tr>
              <th scope="row" class="text-caption text-medium-emphasis">Target</th>
              <td>
                {{ job.target_name }}
                <span v-if="job.target_type === 'group' && job.executor_id">
                  → {{ job.executor_name }}
                </span>
              </td>
            </tr>

            <tr>
              <th scope="row" class="text-caption text-medium-emphasis">Queued At</th>
              <td>{{ formatDateTime(job.queued_at, strTimeZone) }}</td>
            </tr>

            <tr>
              <th scope="row" class="text-caption text-medium-emphasis">Retry At</th>
              <td>{{ formatDateTime(job.retry_at, strTimeZone) }}</td>
            </tr>

            <tr v-if="job.state === JobState.Finished">
              <th scope="row" class="text-caption text-medium-emphasis">Ended At</th>
              <td>{{ formatDateTime(job.ended_at, strTimeZone) }}</td>
            </tr>

            <tr>
              <th scope="row" class="text-caption text-medium-emphasis">Priority</th>
              <td>{{ PRIORITY_LABELS[job.priority] }}</td>
            </tr>

            <tr v-if="job.closed_at">
              <th scope="row" class="text-caption text-medium-emphasis">Closed At</th>
              <td>{{ formatDateTime(job.closed_at, strTimeZone) }}</td>
            </tr>
          </tbody>
        </v-table>
      </v-card-text>
    </v-card>

    <v-card variant="outlined" class="mb-4">
      <v-card-title>Runs</v-card-title>
      <RunTable :runs="job.runs" :time-zone="strTimeZone" />
    </v-card>

    <v-card variant="outlined" class="mb-4">
      <v-card-title>Inputs</v-card-title>

      <v-card-text>
        <RunArgumentsDetails
          snapshot
          :settings="job.run_snapshot"
          :python-environment-name="job.run_snapshot.python_environment_name" />
      </v-card-text>
    </v-card>

    <v-card variant="outlined" class="mb-4">
      <v-card-title>Events</v-card-title>

      <v-table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Event</th>
            <th>Reason</th>
          </tr>
        </thead>

        <tbody>
          <tr v-for="(event, index) in job.events" :key="index">
            <td>{{ formatDateTime(event.occurred_at, strTimeZone) }}</td>
            <td>{{ RUN_EVENT_LABELS[event.kind] }}</td>
            <td>{{ event.reason || "—" }}</td>
          </tr>

          <tr v-if="!job.events.length">
            <td colspan="3">No events.</td>
          </tr>
        </tbody>
      </v-table>
    </v-card>
  </template>
</template>

<script setup lang="ts">
import { shallowRef, computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import JobActions from "@/components/runs/JobActions.vue";
import RunTable from "@/components/runs/RunTable.vue";
import RunArgumentsDetails from "@/components/runSettings/RunArgumentsDetails.vue";

import { JobState, getJob, type JobDetails } from "@/api/runs";
import { getApiError } from "@/api/errors";

import {
  PRIORITY_LABELS,
  JOB_SOURCE_LABELS,
  JOB_STATE_LABELS,
  JOB_STATE_COLORS,
  RUN_EVENT_LABELS,
} from "@/app/runLabels";
import { formatDateTime } from "@/app/formatters";

import { useSessionStore } from "@/stores/sessionStore";

const props = defineProps<{ jobId: string }>();
const sessionStore = useSessionStore();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const job = shallowRef<JobDetails | null>(null);
const boolLoading = ref(false);
const strError = ref("");
let timer: ReturnType<typeof setInterval> | undefined;
let intLoadRevision = 0;

async function load(): Promise<void> {
  const intRevision = ++intLoadRevision;
  boolLoading.value = true;
  strError.value = "";
  try {
    const response = await getJob(props.jobId);
    if (intRevision === intLoadRevision) job.value = response;
  } catch (e) {
    if (intRevision === intLoadRevision) strError.value = getApiError(e).message;
  } finally {
    if (intRevision === intLoadRevision) boolLoading.value = false;
  }
}

watch(
  () => props.jobId,
  () => {
    job.value = null;
    void load();
  },
  { immediate: true },
);

onMounted(() => {
  timer = setInterval(() => {
    if (!document.hidden && !boolLoading.value && job.value?.state !== JobState.Finished)
      void load();
  }, 10000);
});

onBeforeUnmount(() => clearInterval(timer));
</script>

<style scoped></style>
