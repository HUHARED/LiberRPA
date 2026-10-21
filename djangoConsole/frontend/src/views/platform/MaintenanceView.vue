<!-- FileName: MaintenanceView.vue -->
<template>
  <div class="d-flex flex-wrap align-center justify-space-between ga-4 mb-6">
    <h1 class="text-h5">Maintenance</h1>

    <v-btn
      variant="tonal"
      prepend-icon="mdi-refresh"
      :loading="boolLoading"
      :disabled="boolSaving || boolRequestingBackup || sessionStore.busy || !boolCanManage"
      @click="loadPage">
      Refresh
    </v-btn>
  </div>

  <v-alert v-if="accessError" type="error" variant="tonal" class="mb-4" role="alert">
    {{ accessError.message }}
  </v-alert>

  <v-alert v-if="strSuccess" type="success" variant="tonal" class="mb-4" role="status">
    {{ strSuccess }}
  </v-alert>

  <v-card variant="outlined" class="mb-6">
    <v-card-title>Service Maintenance</v-card-title>

    <v-card-text>
      <v-progress-linear v-if="boolMaintenanceLoading" indeterminate class="mb-4" />

      <v-alert
        v-if="maintenanceError"
        type="error"
        variant="tonal"
        class="mb-4"
        role="alert">
        {{ maintenanceError.message }}
        <p v-if="maintenance" class="mt-2">
          Previously loaded service information is shown and may be out of date.
        </p>
      </v-alert>

      <v-alert
        v-if="saveError && maintenanceAction === null"
        type="error"
        variant="tonal"
        class="mb-4"
        role="alert">
        Change was not confirmed. Refresh the service state before trying again.
      </v-alert>

      <template v-if="maintenance">
        <div class="d-flex flex-wrap align-center ga-3 mb-3">
          <span class="text-body-1">Service State</span>
          <v-chip
            :color="maintenance.state === ServiceState.Normal ? 'success' : 'warning'"
            size="small"
            variant="tonal">
            {{ MAP_SERVICE_STATE_LABEL[maintenance.state] }}
          </v-chip>
        </div>
        <p class="text-body-2 mb-2">
          Entered At: {{ formatDateTime(maintenance.entered_at, strTimeZone) }}
        </p>
        <p class="text-body-2 text-medium-emphasis mb-4">
          Updated at {{ formatDateTime(maintenance.updated_at, strTimeZone) }}
        </p>

        <v-table class="mb-4" :aria-busy="boolMaintenanceLoading">
          <thead>
            <tr>
              <th scope="col">Active Jobs</th>
              <th scope="col">Running Runs</th>
              <th scope="col">Jobs Needing Review</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>{{ maintenance.active_jobs }}</td>
              <td>{{ maintenance.running_runs }}</td>
              <td>{{ maintenance.jobs_needing_review }}</td>
            </tr>
          </tbody>
        </v-table>

        <p v-if="maintenance.state === ServiceState.Maintenance" class="text-body-2 mb-3">
          New run requests, schedule triggers, and start permissions are paused. Existing
          runs can continue and report results.
        </p>

        <v-alert
          v-if="maintenance.state === ServiceState.Maintenance && !maintenance.can_resume"
          type="warning"
          variant="tonal">
          {{ maintenance.resume_block_reason }}
        </v-alert>
      </template>
    </v-card-text>

    <v-card-actions v-if="maintenance">
      <v-spacer />
      <v-btn
        v-if="maintenance.state === ServiceState.Normal"
        color="warning"
        variant="tonal"
        prepend-icon="mdi-wrench-outline"
        :disabled="boolActionBlocked"
        @click="openConfirmation(MaintenanceAction.Enter)">
        Enter Maintenance
      </v-btn>
      <v-btn
        v-else
        color="primary"
        variant="tonal"
        prepend-icon="mdi-play-outline"
        :disabled="boolActionBlocked || !maintenance.can_resume"
        @click="openConfirmation(MaintenanceAction.Resume)">
        Resume Service
      </v-btn>
    </v-card-actions>
  </v-card>

  <v-card variant="outlined" class="mb-6">
    <v-card-title>Backups</v-card-title>

    <v-card-text>
      <v-progress-linear v-if="boolBackupsLoading" indeterminate class="mb-4" />

      <v-alert v-if="backupError" type="error" variant="tonal" class="mb-4" role="alert">
        {{ backupError.message }}
        <p v-if="backupStatus" class="mt-2">
          Previously loaded backup information is shown and may be out of date.
        </p>
      </v-alert>

      <v-alert
        v-if="backupRequestError"
        type="error"
        variant="tonal"
        class="mb-4"
        role="alert">
        Backup request was not confirmed. {{ backupRequestError.message }}
        Refresh to check whether a backup is in progress.
      </v-alert>

      <template v-if="backupStatus">
        <v-alert v-if="!backupStatus.configured" type="info" variant="tonal">
          Backups are not configured. Set the backup location and schedule in Console.jsonc.
        </v-alert>

        <template v-else>
          <v-row class="mb-3">
            <v-col cols="12" lg="6">
              <v-text-field
                :model-value="backupStatus.location ?? '—'"
                label="Backup Location"
                variant="underlined"
                readonly
                hide-details />
            </v-col>

            <v-col cols="12" sm="6" lg="3">
              <v-text-field
                :model-value="
                  backupStatus.daily_time ? `Daily at ${backupStatus.daily_time}` : '—'
                "
                label="Backup Schedule"
                variant="underlined"
                readonly
                hide-details />
            </v-col>

            <v-col cols="12" sm="6" lg="3">
              <v-text-field
                :model-value="`${backupStatus.retention_count} successful backups`"
                label="Retention"
                variant="underlined"
                readonly
                hide-details />
            </v-col>
          </v-row>
          <p class="text-body-2 text-medium-emphasis mb-3">
            Location and schedule are managed in Console.jsonc. Instance Time Zone:
            {{ backupStatus.time_zone }}
          </p>
          <p class="text-body-2 mb-2">{{ backupStatus.health_message }}</p>
          <p class="text-body-2 text-medium-emphasis mb-2">
            Display Time Zone: {{ strTimeZone }}
          </p>
          <p class="text-body-2 text-medium-emphasis mb-4">
            Checked at
            {{ formatDateTime(backupStatus.checked_at, strTimeZone) }} · Updated at
            {{ formatDateTime(backupStatus.updated_at, strTimeZone) }}
          </p>

          <h3 class="text-subtitle-1 mb-2">Current Backup</h3>
          <template v-if="backupStatus.current">
            <v-table class="mb-3">
              <thead>
                <tr>
                  <th scope="col">Status</th>
                  <th scope="col">Stage</th>
                  <th scope="col">Started At</th>
                  <th scope="col">Data As Of</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>{{ MAP_BACKUP_STATUS_LABEL[backupStatus.current.status] }}</td>
                  <td>
                    {{
                      backupStatus.current.stage
                        ? MAP_BACKUP_STAGE_LABEL[backupStatus.current.stage]
                        : "—"
                    }}
                  </td>
                  <td class="text-no-wrap">
                    {{ formatDateTime(backupStatus.current.started_at, strTimeZone) }}
                  </td>
                  <td class="text-no-wrap">
                    {{ formatDateTime(backupStatus.current.data_as_of, strTimeZone) }}
                  </td>
                </tr>
              </tbody>
            </v-table>
            <p v-if="backupStatus.current.details" class="text-body-2 mb-4">
              {{ backupStatus.current.details }}
            </p>
          </template>
          <p v-else class="text-body-2 text-medium-emphasis mb-4">No backup in progress.</p>

          <h3 class="text-subtitle-1 mb-2">Latest Result</h3>
          <template v-if="backupStatus.latest_result">
            <v-table class="mb-3">
              <thead>
                <tr>
                  <th scope="col">Status</th>
                  <th scope="col">Data As Of</th>
                  <th scope="col">Started At</th>
                  <th scope="col">Ended At</th>
                  <th scope="col">Size</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>{{ MAP_BACKUP_STATUS_LABEL[backupStatus.latest_result.status] }}</td>
                  <td class="text-no-wrap">
                    {{ formatDateTime(backupStatus.latest_result.data_as_of, strTimeZone) }}
                  </td>
                  <td class="text-no-wrap">
                    {{ formatDateTime(backupStatus.latest_result.started_at, strTimeZone) }}
                  </td>
                  <td class="text-no-wrap">
                    {{ formatDateTime(backupStatus.latest_result.ended_at, strTimeZone) }}
                  </td>
                  <td class="text-no-wrap">
                    {{
                      backupStatus.latest_result.size_bytes === null
                        ? "—"
                        : formatFileSize(backupStatus.latest_result.size_bytes)
                    }}
                  </td>
                </tr>
              </tbody>
            </v-table>
            <p v-if="backupStatus.latest_result.details" class="text-body-2 mb-3">
              {{ backupStatus.latest_result.details }}
            </p>
            <v-alert
              v-if="backupStatus.latest_result.cleanup_error"
              type="warning"
              variant="tonal"
              class="mb-4">
              Old backup cleanup: {{ backupStatus.latest_result.cleanup_error }}
            </v-alert>
          </template>
          <p v-else class="text-body-2 text-medium-emphasis mb-4">No backup result yet.</p>

          <h3 class="text-subtitle-1 mb-2">Last Successful Backup</h3>
          <p v-if="backupStatus.last_success" class="text-body-2 mb-3">
            Completed at
            {{ formatDateTime(backupStatus.last_success.ended_at, strTimeZone) }}
            · Data as of
            {{ formatDateTime(backupStatus.last_success.data_as_of, strTimeZone) }}
            ·
            {{
              backupStatus.last_success.size_bytes === null
                ? "—"
                : formatFileSize(backupStatus.last_success.size_bytes)
            }}
          </p>
          <p v-else class="text-body-2 text-medium-emphasis mb-3">
            No successful backup is available.
          </p>
          <p class="text-body-2 text-medium-emphasis mb-3">
            Data As Of is the time represented by the backup.
          </p>

          <v-alert
            v-if="
              !backupStatus.current &&
              !backupStatus.can_start &&
              backupStatus.blocked_reason
            "
            type="warning"
            variant="tonal">
            {{ backupStatus.blocked_reason }}
          </v-alert>
        </template>
      </template>
    </v-card-text>

    <v-card-actions v-if="backupStatus?.configured">
      <v-spacer />
      <v-btn
        color="primary"
        variant="tonal"
        prepend-icon="mdi-backup-restore"
        :loading="boolRequestingBackup"
        :disabled="boolBackupBlocked"
        @click="startBackup">
        {{ backupStatus.current ? "Backing up…" : "Back Up Now" }}
      </v-btn>
    </v-card-actions>
  </v-card>

  <v-card variant="outlined">
    <v-card-title>Run Activity by Hour</v-card-title>

    <v-card-text>
      <v-progress-linear v-if="boolActivityLoading" indeterminate class="mb-4" />

      <v-alert v-if="activityError" type="error" variant="tonal" class="mb-4" role="alert">
        {{ activityError.message }}
        <p v-if="runActivity" class="mt-2">
          Previously loaded activity is shown and may be out of date.
        </p>
      </v-alert>

      <template v-if="runActivity">
        <p class="text-body-2 mb-2">
          {{ runActivity.start_date }} to {{ runActivity.end_date }} ·
          {{ runActivity.time_zone }}
        </p>
        <p class="text-body-2 text-medium-emphasis mb-3">
          Runs are counted in each hour they overlap. Cleared history is not included.
        </p>
        <p class="text-body-2 text-medium-emphasis mb-4">
          Updated at {{ formatDateTime(runActivity.updated_at, strTimeZone) }}
        </p>

        <v-alert
          v-if="runActivity.incomplete_run_count"
          type="warning"
          variant="tonal"
          class="mb-4">
          {{ runActivity.incomplete_run_count }} retained runs have no confirmed end time
          and are excluded.
        </v-alert>

        <v-table :aria-busy="boolActivityLoading">
          <thead>
            <tr>
              <th scope="col">Hour</th>
              <th scope="col">Run Count</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="entry in runActivity.hours" :key="entry.hour">
              <th scope="row">{{ String(entry.hour).padStart(2, "0") }}:00</th>
              <td>{{ entry.run_count }}</td>
            </tr>
          </tbody>
        </v-table>
      </template>
    </v-card-text>
  </v-card>

  <v-dialog
    :model-value="maintenanceAction !== null"
    max-width="560"
    :persistent="boolSaving"
    @update:model-value="!$event && closeConfirmation()">
    <v-card>
      <v-card-title>
        {{
          maintenanceAction === MaintenanceAction.Enter
            ? "Enter Maintenance"
            : "Resume Service"
        }}
      </v-card-title>

      <v-card-text>
        <v-alert v-if="saveError" type="error" variant="tonal" class="mb-4" role="alert">
          Change was not confirmed. {{ saveError.message }}
        </v-alert>

        <p v-if="maintenanceAction === MaintenanceAction.Enter">
          Pause new run requests, schedule triggers, and start permissions? Waiting jobs and
          retries will be kept. Existing runs will not be stopped and can still report
          results.
        </p>
        <p v-else>Resume run requests, schedule triggers, and new start permissions?</p>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" :disabled="boolSaving" @click="closeConfirmation">
          Cancel
        </v-btn>
        <v-btn
          :color="maintenanceAction === MaintenanceAction.Enter ? 'warning' : 'primary'"
          variant="tonal"
          :loading="boolSaving"
          :disabled="boolSaving || sessionStore.busy || !boolCanManage"
          @click="saveMaintenance">
          {{
            maintenanceAction === MaintenanceAction.Enter
              ? "Enter Maintenance"
              : "Resume Service"
          }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";
import { useDocumentVisibility, useIntervalFn } from "@vueuse/core";

import { useSessionStore } from "@/stores/sessionStore";

import { type ApiError, getApiError } from "@/api/errors";
import { getMaintenance, updateMaintenance, getRunActivity } from "@/api/maintenance";
import { getBackups, requestBackup } from "@/api/backups";
import {
  ServiceState,
  MaintenanceAction,
  type MaintenanceResponse,
  type RunActivityResponse,
  type BackupStage,
  type BackupStatus,
  type BackupStatusResponse,
} from "@/api/generated/browserApi";

import { formatDateTime, formatFileSize } from "@/app/formatters";

const MAP_SERVICE_STATE_LABEL: Record<ServiceState, string> = {
  normal: "Normal",
  maintenance: "Maintenance",
};

const MAP_BACKUP_STATUS_LABEL: Record<BackupStatus, string> = {
  pending: "Queued",
  running: "Running",
  succeeded: "Succeeded",
  failed: "Failed",
  skipped: "Skipped",
};
const MAP_BACKUP_STAGE_LABEL: Record<BackupStage, string> = {
  snapshot: "Preparing snapshot",
  database: "Exporting database",
  files: "Copying files",
  verifying: "Verifying backup",
  finalizing: "Completing backup",
};

const sessionStore = useSessionStore();
const visibility = useDocumentVisibility();
const boolCanManage = computed(() => sessionStore.session?.user.is_platform_admin === true);
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");

const maintenance = shallowRef<MaintenanceResponse | null>(null);
const maintenanceError = shallowRef<ApiError | null>(null);
const boolMaintenanceLoading = ref(false);
let intMaintenanceRevision = 0;

const backupStatus = shallowRef<BackupStatusResponse | null>(null);
const backupError = shallowRef<ApiError | null>(null);
const backupRequestError = shallowRef<ApiError | null>(null);
const boolBackupsLoading = ref(false);
const boolRequestingBackup = ref(false);
let intBackupRevision = 0;

const runActivity = shallowRef<RunActivityResponse | null>(null);
const activityError = shallowRef<ApiError | null>(null);
const boolActivityLoading = ref(false);
let intActivityRevision = 0;

const maintenanceAction = ref<MaintenanceAction | null>(null);
const saveError = shallowRef<ApiError | null>(null);
const strSuccess = ref("");
const boolSaving = ref(false);
const accessError = shallowRef<ApiError | null>(null);
const boolLoading = computed(
  () =>
    boolMaintenanceLoading.value || boolBackupsLoading.value || boolActivityLoading.value,
);
const boolActionBlocked = computed(
  () =>
    boolMaintenanceLoading.value ||
    boolSaving.value ||
    sessionStore.busy ||
    !boolCanManage.value ||
    maintenanceError.value !== null ||
    saveError.value !== null ||
    accessError.value !== null,
);
const boolBackupBlocked = computed(
  () =>
    boolBackupsLoading.value ||
    boolRequestingBackup.value ||
    sessionStore.busy ||
    !boolCanManage.value ||
    !backupStatus.value?.can_start ||
    backupStatus.value.current !== null ||
    backupError.value !== null ||
    backupRequestError.value !== null ||
    accessError.value !== null,
);
let boolUnmounted = false;
const { pause: pauseBackupRefresh, resume: resumeBackupRefresh } = useIntervalFn(
  () => void loadBackups(),
  5000,
  { immediate: false },
);
const boolPollBackups = computed(
  () =>
    visibility.value === "visible" &&
    boolCanManage.value &&
    accessError.value === null &&
    backupStatus.value?.current != null &&
    !boolRequestingBackup.value,
);

async function clearAccessDeniedState(error: ApiError): Promise<void> {
  intMaintenanceRevision += 1;
  intActivityRevision += 1;
  intBackupRevision += 1;
  pauseBackupRefresh();
  maintenance.value = null;
  backupStatus.value = null;
  backupError.value = null;
  backupRequestError.value = null;
  boolBackupsLoading.value = false;
  runActivity.value = null;
  maintenanceError.value = null;
  activityError.value = null;
  maintenanceAction.value = null;
  saveError.value = null;
  strSuccess.value = "";
  boolMaintenanceLoading.value = false;
  boolActivityLoading.value = false;
  accessError.value = error;
  if (error.statusCode === 403) await sessionStore.refreshSession();
}

async function loadMaintenance(): Promise<void> {
  const intCurrentRevision = ++intMaintenanceRevision;
  boolMaintenanceLoading.value = true;
  maintenanceError.value = null;
  try {
    const response = await getMaintenance();
    if (boolUnmounted || intCurrentRevision !== intMaintenanceRevision) return;
    maintenance.value = response;
  } catch (e) {
    if (boolUnmounted || intCurrentRevision !== intMaintenanceRevision) return;
    const error = getApiError(e);
    if ([401, 403].includes(error.statusCode)) await clearAccessDeniedState(error);
    else maintenanceError.value = error;
  } finally {
    if (!boolUnmounted && intCurrentRevision === intMaintenanceRevision)
      boolMaintenanceLoading.value = false;
  }
}

async function loadBackups(): Promise<void> {
  if (
    boolUnmounted ||
    boolBackupsLoading.value ||
    boolRequestingBackup.value ||
    !boolCanManage.value ||
    accessError.value !== null
  )
    return;
  const intCurrentRevision = ++intBackupRevision;
  boolBackupsLoading.value = true;
  backupError.value = null;
  try {
    const response = await getBackups();
    if (boolUnmounted || intCurrentRevision !== intBackupRevision) return;
    backupStatus.value = response;
    backupRequestError.value = null;
  } catch (e) {
    if (boolUnmounted || intCurrentRevision !== intBackupRevision) return;
    const error = getApiError(e);
    if ([401, 403].includes(error.statusCode)) await clearAccessDeniedState(error);
    else backupError.value = error;
  } finally {
    if (!boolUnmounted && intCurrentRevision === intBackupRevision)
      boolBackupsLoading.value = false;
  }
}

async function startBackup(): Promise<void> {
  if (boolUnmounted || boolBackupBlocked.value) return;
  const intCurrentRevision = ++intBackupRevision;
  boolRequestingBackup.value = true;
  backupRequestError.value = null;
  try {
    const response = await requestBackup();
    if (boolUnmounted || intCurrentRevision !== intBackupRevision) return;
    backupStatus.value = response;
  } catch (e) {
    if (boolUnmounted || intCurrentRevision !== intBackupRevision) return;
    const error = getApiError(e);
    if ([401, 403].includes(error.statusCode)) await clearAccessDeniedState(error);
    else backupRequestError.value = error;
  } finally {
    if (!boolUnmounted) boolRequestingBackup.value = false;
  }
}

async function loadActivity(): Promise<void> {
  const intCurrentRevision = ++intActivityRevision;
  boolActivityLoading.value = true;
  activityError.value = null;
  try {
    const response = await getRunActivity();
    if (boolUnmounted || intCurrentRevision !== intActivityRevision) return;
    runActivity.value = response;
  } catch (e) {
    if (boolUnmounted || intCurrentRevision !== intActivityRevision) return;
    const error = getApiError(e);
    if ([401, 403].includes(error.statusCode)) await clearAccessDeniedState(error);
    else activityError.value = error;
  } finally {
    if (!boolUnmounted && intCurrentRevision === intActivityRevision)
      boolActivityLoading.value = false;
  }
}

async function loadPage(): Promise<void> {
  if (
    boolUnmounted ||
    boolLoading.value ||
    boolSaving.value ||
    boolRequestingBackup.value ||
    !boolCanManage.value
  )
    return;
  accessError.value = null;
  saveError.value = null;
  strSuccess.value = "";
  await Promise.all([loadMaintenance(), loadBackups(), loadActivity()]);
}

function openConfirmation(action: MaintenanceAction): void {
  if (
    boolActionBlocked.value ||
    !maintenance.value ||
    (action === MaintenanceAction.Resume && !maintenance.value.can_resume)
  )
    return;
  saveError.value = null;
  strSuccess.value = "";
  maintenanceAction.value = action;
}

function closeConfirmation(): void {
  if (boolSaving.value) return;
  maintenanceAction.value = null;
}

async function saveMaintenance(): Promise<void> {
  const action = maintenanceAction.value;
  if (
    boolUnmounted ||
    action === null ||
    boolSaving.value ||
    sessionStore.busy ||
    !boolCanManage.value
  )
    return;
  boolSaving.value = true;
  saveError.value = null;
  strSuccess.value = "";
  const intCurrentRevision = ++intMaintenanceRevision;
  try {
    const response = await updateMaintenance({ action });
    if (boolUnmounted || intCurrentRevision !== intMaintenanceRevision) return;
    maintenance.value = response;
    maintenanceError.value = null;
    maintenanceAction.value = null;
    strSuccess.value =
      response.state === ServiceState.Maintenance
        ? "Maintenance is active."
        : "Service resumed.";
  } catch (e) {
    if (boolUnmounted || intCurrentRevision !== intMaintenanceRevision) return;
    const error = getApiError(e);
    if ([401, 403].includes(error.statusCode)) await clearAccessDeniedState(error);
    else saveError.value = error;
  } finally {
    if (!boolUnmounted) boolSaving.value = false;
  }
}

watch(boolPollBackups, (boolPolling) => {
  if (boolPolling) resumeBackupRefresh();
  else pauseBackupRefresh();
});

watch(visibility, (state, previousState) => {
  if (state === "visible" && previousState !== "visible") void loadBackups();
});

onMounted(() => void loadPage());
onBeforeUnmount(() => {
  boolUnmounted = true;
  pauseBackupRefresh();
  intBackupRevision += 1;
  intMaintenanceRevision += 1;
  intActivityRevision += 1;
});
</script>

<style scoped></style>
