<!-- FileName: JobDetailsView.vue -->
<template>
  <div class="d-flex align-center ga-2 mb-4">
    <v-btn to="/jobs" variant="text" prepend-icon="mdi-arrow-left">Job Queue</v-btn>
    <v-spacer />
    <v-btn variant="tonal" :loading="boolLoading" @click="load">Refresh</v-btn>
  </div>
  <v-alert v-if="strError" type="error" variant="tonal" class="mb-4">
    {{ strError }}
  </v-alert>
  <template v-if="job">
    <div class="d-flex align-center flex-wrap ga-3 mb-4">
      <h1 class="text-h5">{{ job.project_name }} · {{ job.version }}</h1>
      <v-chip>{{ getStateLabel(job.state) }}</v-chip>
      <v-spacer />
      <JobActions :job="job" @updated="load" @error="strError = $event" />
    </div>
    <v-alert
      v-if="job.reason"
      :type="job.state === 'needs_review' ? 'warning' : 'info'"
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
              <td>Source</td>
              <td>{{ getStateLabel(job.source) }}</td>
            </tr>
            <tr>
              <td>Schedule</td>
              <td>{{ job.schedule_name || "—" }}</td>
            </tr>
            <tr>
              <td>Scheduled At</td>
              <td>{{ formatDateTime(job.scheduled_at, strTimeZone) }}</td>
            </tr>
            <tr>
              <td>Target</td>
              <td>
                {{ job.target_name }}
                <span v-if="job.target_type === 'group' && job.executor_id">
                  → {{ job.executor_name }}
                </span>
              </td>
            </tr>
            <tr>
              <td>Queued At</td>
              <td>{{ formatDateTime(job.queued_at, strTimeZone) }}</td>
            </tr>
            <tr>
              <td>Retry At</td>
              <td>{{ formatDateTime(job.retry_at, strTimeZone) }}</td>
            </tr>
            <tr>
              <td>Priority</td>
              <td>{{ getStateLabel(job.priority) }}</td>
            </tr>
            <tr v-if="job.closed_at">
              <td>Closed At</td>
              <td>{{ formatDateTime(job.closed_at, strTimeZone) }}</td>
            </tr>
          </tbody>
        </v-table>
      </v-card-text>
    </v-card>
    <v-card variant="outlined" class="mb-4">
      <v-card-title>Runs</v-card-title>
      <RunTable :runs="job.runs" :time-zone="strTimeZone" show-attempt />
    </v-card>
    <v-card variant="outlined" class="mb-4">
      <v-card-title>Inputs</v-card-title>
      <v-card-text><RunInputs :inputs="job.inputs" /></v-card-text>
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
            <td>{{ getStateLabel(event.kind) }}</td>
            <td>{{ event.reason || "—" }}</td>
          </tr>
          <tr v-if="!job.events.length">
            <td colspan="3">No events.</td>
          </tr>
        </tbody>
      </v-table>
    </v-card>
    <v-expansion-panels>
      <v-expansion-panel title="Identifiers">
        <v-expansion-panel-text>
          <p>Job ID: {{ job.id }}</p>
          <p>Job Request ID: {{ job.job_request_id }}</p>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>
  </template>
</template>
<script setup lang="ts">
import { shallowRef, computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import JobActions from "@/components/runs/JobActions.vue";
import RunTable from "@/components/runs/RunTable.vue";
import RunInputs from "@/components/runOptions/RunInputs.vue";
import { getJob, getStateLabel, type JobDetails } from "@/api/runs";
import { getApiError } from "@/api/errors";
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
    if (!document.hidden && !boolLoading.value && job.value?.state !== "finished")
      void load();
  }, 10000);
});
onBeforeUnmount(() => clearInterval(timer));
</script>
<style scoped></style>
