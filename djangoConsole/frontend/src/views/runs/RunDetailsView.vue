<!-- FileName: RunDetailsView.vue -->
<template>
  <div class="d-flex align-center flex-wrap ga-3 mb-4">
    <v-btn to="/runs" variant="text" prepend-icon="mdi-arrow-left">Run History</v-btn>
    <v-spacer />
    <v-btn :loading="boolLoading" variant="tonal" @click="load">Refresh</v-btn>
    <v-btn v-if="run" :disabled="boolBusy" variant="tonal" @click="rerun">Rerun</v-btn>
    <v-btn
      v-if="run?.can_stop"
      :loading="boolBusy"
      color="warning"
      variant="tonal"
      @click="stop">
      Stop Run
    </v-btn>
  </div>
  <v-alert v-if="strError" type="error" variant="tonal" class="mb-4">
    {{ strError }}
  </v-alert>
  <template v-if="run">
    <h1 class="text-h5 mb-3">{{ run.project_name }} · {{ run.version }}</h1>
    <v-card variant="outlined" class="mb-4">
      <v-card-text>
        <v-row>
          <v-col cols="12" md="4">
            <p>
              <v-chip>{{ getStateLabel(run.result) }}</v-chip>
            </p>
            <p class="mt-2">Executor: {{ run.executor_name }}</p>
            <p>Account: {{ run.account_name }}</p>
          </v-col>
          <v-col cols="12" md="8">
            <p>Started At: {{ formatDateTime(run.started_at, strTimeZone) }}</p>
            <p>
              Ended At:
              {{ run.ended_at ? formatDateTime(run.ended_at, strTimeZone) : "Unknown" }}
            </p>
            <p v-if="run.reason" class="text-pre-wrap">{{ run.reason }}</p>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>
    <v-tabs v-model="strTab">
      <v-tab value="logs">Logs</v-tab>
      <v-tab value="inputs">Inputs</v-tab>
      <v-tab value="outputs">Outputs</v-tab>
      <v-tab value="details">Details</v-tab>
    </v-tabs>
    <v-card variant="outlined" class="mt-4">
      <v-card-text>
        <RunLogs
          v-show="strTab === 'logs'"
          :key="run.id"
          :run-id="run.id"
          :running="run.result === 'running'"
          :time-zone="strTimeZone"
          :active="strTab === 'logs'"
          :download-enabled="run.files.logs.available"
          :download-reason="run.files.logs.reason"
          @download="download('logs')" />
        <RunInputs v-if="strTab === 'inputs'" :inputs="run.inputs" />
        <template v-if="strTab === 'outputs'">
          <v-alert v-if="run.outputs_status === 'waiting'" type="info" variant="tonal">
            Waiting for the final outputs.
          </v-alert>
          <v-alert
            v-else-if="run.outputs_status === 'unavailable'"
            type="warning"
            variant="tonal">
            Outputs unavailable. {{ run.outputs_reason }}
          </v-alert>
          <template v-else>
            <v-alert
              v-if="run.outputs_status === 'partial'"
              type="warning"
              variant="tonal"
              class="mb-4">
              Some outputs are unavailable. {{ run.outputs_reason }}
            </v-alert>
            <p
              v-if="
                run.outputs_status === 'complete' &&
                run.outputs &&
                Object.keys(run.outputs).length === 0
              ">
              No output items.
            </p>
            <v-table v-else>
              <thead>
                <tr>
                  <th>Key</th>
                  <th>Value</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(value, key) in run.outputs ?? {}" :key="key">
                  <td>{{ key }}</td>
                  <td>
                    <pre class="text-pre-wrap text-break py-2">{{
                      formatJsonValue(value)
                    }}</pre>
                  </td>
                </tr>
                <tr
                  v-for="name in run.outputs_unavailable_keys"
                  :key="`unavailable:${name}`">
                  <td>{{ name }}</td>
                  <td>Unavailable</td>
                </tr>
              </tbody>
            </v-table>
          </template>
        </template>
        <template v-if="strTab === 'details'">
          <h2 class="text-h6 mb-3">Job Information</h2>
          <v-table>
            <tbody>
              <tr>
                <td>Department</td>
                <td>
                  {{ run.department_path }}
                  <span v-if="run.department_deleted_at !== null">(Deleted)</span>
                </td>
              </tr>
              <tr>
                <td>Source</td>
                <td>{{ getStateLabel(run.job.source) }}</td>
              </tr>
              <tr>
                <td>Schedule</td>
                <td>{{ run.job.schedule_name || "—" }}</td>
              </tr>
              <tr>
                <td>Scheduled At</td>
                <td>{{ formatDateTime(run.job.scheduled_at, strTimeZone) }}</td>
              </tr>
              <tr>
                <td>Original Target</td>
                <td>{{ run.job.target_name }}</td>
              </tr>
              <tr>
                <td>Queued At</td>
                <td>{{ formatDateTime(run.job.queued_at, strTimeZone) }}</td>
              </tr>
              <tr>
                <td>Job</td>
                <td>
                  <RouterLink :to="{ name: 'job-details', params: { jobId: run.job_id } }">
                    View Job
                  </RouterLink>
                </td>
              </tr>
            </tbody>
          </v-table>
          <h2 class="text-h6 my-4">Result &amp; Events</h2>
          <p>{{ run.reason || "No additional result message." }}</p>
          <pre
            v-if="Object.keys(run.error_summary ?? {}).length"
            class="text-pre-wrap text-break mt-3"
            >{{ formatJsonValue(run.error_summary) }}</pre>
          <h2 class="text-h6 mt-5 mb-2">Other Runs in This Job</h2>
          <p class="mb-3">Current attempt: {{ run.attempt }}</p>
          <RunTable
            :runs="run.other_runs"
            :time-zone="strTimeZone"
            show-attempt
            empty-text="No other runs." />
          <h2 class="text-h6 mt-5 mb-3">Video</h2>
          <p v-if="!run.inputs.builtin_record_video">
            Recording was not enabled for this run.
          </p>
          <template v-else>
            <p class="mb-3">Files are stored on the Executor.</p>
            <v-alert
              v-if="run.recording.status !== 'ready'"
              type="info"
              variant="tonal"
              class="mb-3">
              {{
                run.recording.reason ||
                `Recording status: ${run.recording.status || "unknown"}.`
              }}
            </v-alert>
            <v-table>
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Size</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Video</td>
                  <td>
                    {{
                      typeof run.recording.videoSizeBytes === "number"
                        ? formatFileSize(run.recording.videoSizeBytes)
                        : "Unknown"
                    }}
                  </td>
                  <td>
                    <v-btn
                      :disabled="!run.files.video.available"
                      :loading="boolDownloading"
                      variant="text"
                      @click="download('video')">
                      Download Video
                    </v-btn>
                    <p class="text-caption">{{ run.files.video.reason }}</p>
                  </td>
                </tr>
                <tr v-if="typeof run.recording.subtitleSizeBytes === 'number'">
                  <td>Subtitles</td>
                  <td>{{ formatFileSize(run.recording.subtitleSizeBytes) }}</td>
                  <td>
                    <v-btn
                      :disabled="!run.files.subtitles.available"
                      :loading="boolDownloading"
                      variant="text"
                      @click="download('subtitles')">
                      Download Subtitles
                    </v-btn>
                    <p class="text-caption">{{ run.files.subtitles.reason }}</p>
                  </td>
                </tr>
              </tbody>
            </v-table>
          </template>
          <v-expansion-panels class="mt-5">
            <v-expansion-panel title="Identifiers">
              <v-expansion-panel-text>
                <p>Job ID: {{ run.job_id }}</p>
                <p>Run ID: {{ run.id }}</p>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </template>
      </v-card-text>
    </v-card>
  </template>
  <RunPackageDialog
    v-if="rerunInfo"
    :package-id="rerunInfo.package_id"
    :executor-ids="rerunInfo.executor_ids"
    :group-id="rerunInfo.group_id"
    :original-job-active="rerunInfo.original_job_active"
    @close="rerunInfo = null"
    @saved="created" />
</template>
<script setup lang="ts">
import { shallowRef, computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink, useRouter } from "vue-router";
import RunInputs from "@/components/runOptions/RunInputs.vue";
import RunLogs from "@/components/runs/RunLogs.vue";
import RunTable from "@/components/runs/RunTable.vue";
import RunPackageDialog from "@/components/packages/RunPackageDialog.vue";
import {
  getRun,
  getRerun,
  stopRun,
  downloadRunFile,
  getStateLabel,
  type RunDetails,
} from "@/api/runs";
import { formatJsonValue } from "@/api/runOptions";
import { getApiError } from "@/api/errors";
import { formatDateTime, formatFileSize } from "@/app/formatters";
import { useSessionStore } from "@/stores/sessionStore";
const props = defineProps<{ runId: string }>();
const sessionStore = useSessionStore();
const router = useRouter();
const run = shallowRef<RunDetails | null>(null);
const strTab = ref("logs");
const boolLoading = ref(false);
const boolBusy = ref(false);
const boolDownloading = ref(false);
const strError = ref("");
const rerunInfo = ref<Awaited<ReturnType<typeof getRerun>> | null>(null);
let timer: ReturnType<typeof setInterval> | undefined;
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");

let intLoadRevision = 0;
async function load(): Promise<void> {
  const intRevision = ++intLoadRevision;
  boolLoading.value = true;
  strError.value = "";
  try {
    const response = await getRun(props.runId);
    if (intRevision === intLoadRevision) run.value = response;
  } catch (e) {
    if (intRevision === intLoadRevision) strError.value = getApiError(e).message;
  } finally {
    if (intRevision === intLoadRevision) boolLoading.value = false;
  }
}
async function stop(): Promise<void> {
  boolBusy.value = true;
  strError.value = "";
  try {
    await stopRun(props.runId);
    await load();
  } catch (e) {
    strError.value = getApiError(e).message;
  } finally {
    boolBusy.value = false;
  }
}
async function rerun(): Promise<void> {
  boolBusy.value = true;
  strError.value = "";
  try {
    rerunInfo.value = await getRerun(props.runId);
  } catch (e) {
    strError.value = getApiError(e).message;
  } finally {
    boolBusy.value = false;
  }
}
async function download(kind: "logs" | "video" | "subtitles"): Promise<void> {
  boolDownloading.value = true;
  strError.value = "";
  try {
    await downloadRunFile(props.runId, kind);
  } catch (e) {
    strError.value = getApiError(e).message;
  } finally {
    boolDownloading.value = false;
  }
}
function created(): void {
  rerunInfo.value = null;
  void router.push({ name: "job-queue" });
}
watch(
  () => props.runId,
  () => {
    run.value = null;
    strTab.value = "logs";
    void load();
  },
  { immediate: true },
);
onMounted(() => {
  timer = setInterval(() => {
    if (!document.hidden && !boolLoading.value && run.value?.result === "running")
      void load();
  }, 10000);
});
onBeforeUnmount(() => clearInterval(timer));
</script>
<style scoped></style>
