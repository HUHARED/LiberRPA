<!-- FileName: RunDetailsView.vue -->
<template>
  <div class="d-flex align-center flex-wrap ga-3 mb-4">
    <v-btn to="/runs" variant="tonal" prepend-icon="mdi-arrow-left">
      Back to Run History
    </v-btn>
    <v-spacer />
    <v-btn :loading="boolLoading" variant="tonal" prepend-icon="mdi-refresh" @click="load">
      Refresh
    </v-btn>

    <v-btn
      v-if="run"
      v-tooltip:bottom="'Run Most Recently Uploaded Version'"
      :disabled="boolBusy || !run.can_rerun"
      variant="tonal"
      prepend-icon="mdi-replay"
      @click="rerun">
      Rerun
    </v-btn>

    <v-btn
      v-if="run?.can_stop"
      :loading="boolBusy"
      color="warning"
      variant="tonal"
      prepend-icon="mdi-stop-circle-outline"
      @click="stop">
      Stop Run
    </v-btn>

    <span v-if="run?.stop_requested" class="text-body-2">Stop requested</span>
  </div>

  <v-alert v-if="strError" type="error" variant="tonal" class="mb-4">
    {{ strError }}
  </v-alert>

  <template v-if="run">
    <h1 class="text-h5 mb-3">{{ run.project_name }} · {{ run.project_version }}</h1>

    <v-card variant="outlined" class="mb-4">
      <v-card-text>
        <v-chip
          :border="`${RUN_STATUS_COLORS[run.status]} thin opacity-25`"
          :color="RUN_STATUS_COLORS[run.status]"
          :text="RUN_STATUS_LABELS[run.status]"
          variant="text"
          size="x-small"
          class="mb-4" />

        <v-row>
          <v-col cols="12" md="6">
            <v-textarea
              :model-value="run.executor_name"
              label="Executor"
              variant="plain"
              density="compact"
              rows="1"
              auto-grow
              readonly
              hide-details />
          </v-col>

          <v-col cols="12" md="6">
            <v-textarea
              :model-value="run.account_name"
              label="Account"
              variant="plain"
              density="compact"
              rows="1"
              auto-grow
              readonly
              hide-details />
          </v-col>

          <v-col cols="12" md="6">
            <v-text-field
              :model-value="formatDateTime(run.started_at, strTimeZone)"
              label="Started At"
              variant="plain"
              density="compact"
              readonly
              hide-details />
          </v-col>

          <v-col cols="12" md="6">
            <v-text-field
              :model-value="formatRunEndTime(run, strTimeZone)"
              label="Ended At"
              variant="plain"
              density="compact"
              readonly
              hide-details />
          </v-col>
        </v-row>

        <p v-if="run.reason" class="text-pre-wrap text-break mt-3">{{ run.reason }}</p>
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
        <!-- NOTE: Apply v-show to a DOM element because RunLogs has multiple roots. -->
        <div v-show="strTab === 'logs'">
          <RunLogs
            :key="run.id"
            :run-id="run.id"
            :running="run.status === RunStatus.Running"
            :time-zone="strTimeZone"
            :active="strTab === 'logs'"
            :download-enabled="run.files.logs.available"
            :download-reason="run.files.logs.reason"
            @refresh="load"
            @download="download(RunFileKind.Logs)" />
        </div>

        <RunArgumentsDetails
          v-if="strTab === 'inputs'"
          snapshot
          :settings="run.run_snapshot"
          :python-environment-name="run.run_snapshot.python_environment_name" />

        <template v-if="strTab === 'outputs'">
          <v-alert
            v-if="run.outputs_status === OutputsStatus.Waiting"
            type="info"
            variant="tonal">
            Waiting for the final outputs.
          </v-alert>

          <v-alert
            v-else-if="run.outputs_status === OutputsStatus.Unavailable"
            type="warning"
            variant="tonal">
            Outputs unavailable. {{ run.outputs_reason }}
          </v-alert>

          <template v-else>
            <v-alert
              v-if="run.outputs_status === OutputsStatus.Partial"
              type="warning"
              variant="tonal"
              class="mb-4">
              Some outputs are unavailable. {{ run.outputs_reason }}
            </v-alert>

            <p
              v-if="
                run.outputs_status === OutputsStatus.Complete &&
                run.outputs &&
                run.outputs.length === 0
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
                <tr v-for="[key, value] in run.outputs ?? []" :key="`value:${key}`">
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
                <th scope="row" class="text-caption text-medium-emphasis">Department</th>
                <td>
                  {{ run.department_path }}
                  <span v-if="run.department_deleted_at !== null">(Deleted)</span>
                </td>
              </tr>

              <tr>
                <th scope="row" class="text-caption text-medium-emphasis">Source</th>
                <td>{{ JOB_SOURCE_LABELS[run.job.source] }}</td>
              </tr>

              <tr>
                <th scope="row" class="text-caption text-medium-emphasis">Schedule</th>
                <td>{{ run.job.schedule_name || "—" }}</td>
              </tr>

              <tr>
                <th scope="row" class="text-caption text-medium-emphasis">Scheduled At</th>
                <td>{{ formatDateTime(run.job.scheduled_at, strTimeZone) }}</td>
              </tr>

              <tr>
                <th scope="row" class="text-caption text-medium-emphasis">
                  Original Target
                </th>
                <td>{{ run.job.target_name }}</td>
              </tr>

              <tr>
                <th scope="row" class="text-caption text-medium-emphasis">Queued At</th>
                <td>{{ formatDateTime(run.job.queued_at, strTimeZone) }}</td>
              </tr>

              <tr>
                <th scope="row" class="text-caption text-medium-emphasis">Job</th>
                <td>
                  <RouterLink
                    :to="{ name: 'job-details', params: { jobId: run.job_id } }"
                    class="text-primary text-decoration-none">
                    View Job
                  </RouterLink>
                </td>
              </tr>
            </tbody>
          </v-table>

          <template v-if="Object.keys(run.error_summary ?? {}).length">
            <h2 class="text-h6 my-4">Error Details</h2>

            <pre class="text-pre-wrap text-break mt-3">{{
              formatJsonValue(run.error_summary)
            }}</pre>
          </template>

          <h2 class="text-h6 mt-5 mb-2">Other Runs in This Job</h2>

          <p class="mb-3">
            <span class="text-caption text-medium-emphasis">Current attempt:</span>
            {{ run.attempt_number }}
          </p>

          <RunTable
            :runs="run.other_runs"
            :time-zone="strTimeZone"
            empty-text="No other runs." />

          <h2 class="text-h6 mt-5 mb-3">Video</h2>

          <p v-if="!run.run_snapshot.builtin_record_video">
            Recording was not enabled for this run.
          </p>

          <template v-else>
            <v-alert
              v-if="run.recording.status !== RecordingStatus.Ready"
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
                      v-tooltip:bottom="
                        `Download Video. Please use your browser's built-in downloader.`
                      "
                      :disabled="!run.files.video.available"
                      :loading="boolDownloading"
                      variant="text"
                      size="small"
                      aria-label="Download Video"
                      icon="mdi-download"
                      @click="download(RunFileKind.Video)" />

                    <p v-if="run.files.video.reason" class="text-caption">
                      {{ run.files.video.reason }}
                    </p>
                  </td>
                </tr>

                <tr v-if="typeof run.recording.subtitleSizeBytes === 'number'">
                  <td>Subtitles</td>
                  <td>{{ formatFileSize(run.recording.subtitleSizeBytes) }}</td>
                  <td>
                    <v-btn
                      v-tooltip:bottom="
                        `Download Subtitles. Please use your browser's built-in downloader.`
                      "
                      :disabled="!run.files.subtitles.available"
                      :loading="boolDownloading"
                      variant="text"
                      size="small"
                      aria-label="Download Subtitles"
                      icon="mdi-download"
                      @click="download(RunFileKind.Subtitles)" />

                    <p v-if="run.files.subtitles.reason" class="text-caption">
                      {{ run.files.subtitles.reason }}
                    </p>
                  </td>
                </tr>
              </tbody>
            </v-table>
          </template>
        </template>
      </v-card-text>
    </v-card>
  </template>

  <PackageRunDialog
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

import RunArgumentsDetails from "@/components/runSettings/RunArgumentsDetails.vue";
import RunLogs from "@/components/runs/RunLogs.vue";
import RunTable from "@/components/runs/RunTable.vue";
import PackageRunDialog from "@/components/packages/PackageRunDialog.vue";

import {
  RunStatus,
  OutputsStatus,
  RecordingStatus,
  getRun,
  getRerun,
  stopRun,
  downloadRunFile,
  RunFileKind,
  type RunDetails,
} from "@/api/runs";
import { getApiError } from "@/api/errors";

import { JOB_SOURCE_LABELS, RUN_STATUS_LABELS, RUN_STATUS_COLORS } from "@/app/runLabels";
import {
  formatDateTime,
  formatRunEndTime,
  formatFileSize,
  formatJsonValue,
} from "@/app/formatters";

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
  if (boolBusy.value || !run.value?.can_rerun) return;
  const strRunId = props.runId;
  boolBusy.value = true;
  strError.value = "";
  try {
    const response = await getRerun(strRunId);
    if (props.runId === strRunId) rerunInfo.value = response;
  } catch (e) {
    if (props.runId === strRunId) strError.value = getApiError(e).message;
  } finally {
    boolBusy.value = false;
  }
}

async function download(kind: RunFileKind): Promise<void> {
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
    rerunInfo.value = null;
    strTab.value = "logs";
    void load();
  },
  { immediate: true },
);

onMounted(() => {
  timer = setInterval(() => {
    if (
      !document.hidden &&
      !boolLoading.value &&
      run.value &&
      (run.value.status === RunStatus.Running ||
        (run.value.run_snapshot.builtin_record_video &&
          run.value.recording.status !== RecordingStatus.Ready &&
          run.value.recording.status !== RecordingStatus.Unavailable))
    )
      void load();
  }, 10000);
});

onBeforeUnmount(() => clearInterval(timer));
</script>

<style scoped></style>
