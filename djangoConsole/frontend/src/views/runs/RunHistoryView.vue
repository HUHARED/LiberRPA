<!-- FileName: RunHistoryView.vue -->
<template>
  <div class="d-flex align-center flex-wrap ga-3 mb-4">
    <h1 class="text-h5">Run History</h1>
    <v-spacer />
    <v-btn variant="tonal" :loading="boolLoading" @click="load()">Refresh</v-btn>
  </div>
  <v-card variant="outlined" class="mb-4">
    <v-card-text>
      <form @submit.prevent="apply">
        <v-row>
          <v-col cols="12" md="4">
            <v-select
              v-model="filters.departmentIds"
              :items="arrDepartment"
              :item-title="
                (department: RunDepartmentInfo) =>
                  `${department.path}${department.deleted_at ? ' (Archived)' : ''}`
              "
              item-value="id"
              label="Department"
              multiple
              chips
              hide-details />
          </v-col>
          <v-col cols="12" md="4">
            <v-text-field v-model="filters.scheduleName" label="Schedule" hide-details />
          </v-col>
          <v-col cols="12" md="4">
            <v-text-field v-model="filters.projectName" label="Project" hide-details />
          </v-col>
          <v-col cols="12" md="4">
            <v-select
              v-model="filters.results"
              :items="
                ARR_RUN_RESULT.map((value) => ({ value, title: RUN_RESULT_LABELS[value] }))
              "
              label="Status"
              multiple
              chips
              hide-details />
          </v-col>
          <v-col cols="12" md="4">
            <v-text-field
              v-model="filters.startedFrom"
              label="Started From"
              type="datetime-local"
              step="1"
              :hint="strTimeZone"
              persistent-hint />
          </v-col>
          <v-col cols="12" md="4">
            <v-text-field
              v-model="filters.startedUntil"
              label="Started Before"
              type="datetime-local"
              step="1"
              :hint="strTimeZone"
              persistent-hint />
          </v-col>
        </v-row>
        <div class="d-flex ga-2 mt-4">
          <v-btn type="submit" color="primary" variant="tonal">Apply</v-btn>
          <v-btn variant="outlined" @click="clearFilters">Clear Filters</v-btn>
        </div>
      </form>
    </v-card-text>
  </v-card>
  <v-alert v-if="strError" type="error" variant="tonal" class="mb-4">
    {{ strError }}
  </v-alert>
  <v-alert v-if="clearResult" type="info" variant="tonal" class="mb-4">
    <p>
      Cleared: {{ clearResult.cleared }} · Skipped: {{ clearResult.skipped.length }} ·
      Failed: {{ clearResult.failed.length }}
    </p>
    <p v-for="entry in [...clearResult.skipped, ...clearResult.failed]" :key="entry.id">
      {{ entry.id }}: {{ entry.reason }}
    </p>
  </v-alert>
  <div class="d-flex align-center flex-wrap ga-3 mb-3">
    <span>{{ arrSelectedId.length }} selected</span>
    <v-btn
      size="small"
      variant="tonal"
      :disabled="!page?.total_count || boolSelecting || boolLoading"
      :loading="boolSelecting"
      @click="selectAll">
      Select All Matching Runs
    </v-btn>
    <v-btn
      size="small"
      variant="text"
      :disabled="!arrSelectedId.length && !boolSelecting"
      @click="clearSelection">
      Clear Selection
    </v-btn>
    <v-spacer />
    <v-btn
      color="warning"
      variant="tonal"
      :disabled="!arrSelectedId.length || boolSelecting || boolLoading || boolClearing"
      @click="confirmClear">
      Clear Logs
    </v-btn>
  </div>
  <v-card variant="outlined">
    <v-data-table-server
      :model-value="arrSelectedId"
      :headers="ARR_HEADER"
      :items="page?.runs ?? []"
      :items-length="page?.total_count ?? 0"
      :items-per-page="50"
      :loading="boolLoading"
      item-value="id"
      show-select
      select-strategy="page"
      disable-sort
      hide-default-footer
      @update:model-value="updateSelection">
      <template #item.schedule_name="{ item }">{{ item.schedule_name || "—" }}</template>
      <template #item.started_at="{ item }">
        {{ formatDateTime(item.started_at, strTimeZone) }}
      </template>
      <template #item.ended_at="{ item }">
        {{ item.ended_at ? formatDateTime(item.ended_at, strTimeZone) : "Unknown" }}
      </template>
      <template #item.result="{ item }">{{ RUN_RESULT_LABELS[item.result] }}</template>
      <template #item.actions="{ item }">
        <div class="d-flex">
          <v-btn
            :to="{ name: 'run-details', params: { runId: item.id } }"
            size="small"
            variant="text">
            View
          </v-btn>
          <v-btn
            size="small"
            variant="text"
            :disabled="boolActionBusy || !item.can_rerun"
            @click="rerun(item.id)">
            Rerun
          </v-btn>
          <v-btn
            v-if="item.can_stop"
            size="small"
            color="warning"
            variant="text"
            :disabled="boolActionBusy"
            @click="stop(item.id)">
            Stop Run
          </v-btn>
        </div>
      </template>
      <template #no-data>No runs match the current filters.</template>
    </v-data-table-server>
    <v-divider />
    <div class="d-flex align-center justify-space-between pa-3">
      <span>{{ page?.total_count ?? 0 }} runs</span>
      <v-pagination
        v-if="page && page.total_pages > 1"
        :model-value="page.page"
        :length="page.total_pages"
        :total-visible="5"
        :disabled="boolLoading"
        @update:model-value="load" />
    </div>
  </v-card>
  <v-dialog v-model="boolClearDialog" persistent max-width="640">
    <v-card>
      <v-card-title>Clear Logs</v-card-title>
      <v-card-text>
        <p>
          Clear logs from Console for {{ arrConfirmedId.length }} selected runs? Run
          summaries, inputs, outputs and files on Executors are retained. Protected runs are
          skipped.
        </p>
        <v-alert v-if="strClearError" type="error" variant="tonal" class="mt-4">
          {{ strClearError }}
        </v-alert>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn :disabled="boolClearing" @click="boolClearDialog = false">Cancel</v-btn>
        <v-btn color="warning" :loading="boolClearing" @click="clearLogs">Clear Logs</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
  <RunPackageDialog
    v-if="rerunInfo"
    :package-id="rerunInfo.package_id"
    :executor-ids="rerunInfo.executor_ids"
    :group-id="rerunInfo.group_id"
    :original-job-active="rerunInfo.original_job_active"
    @close="rerunInfo = null"
    @saved="runCreated" />
</template>
<script setup lang="ts">
import { shallowRef, computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import RunPackageDialog from "@/components/packages/RunPackageDialog.vue";
import {
  ARR_RUN_RESULT,
  getRuns,
  getMatchingRunIds,
  getRunDepartments,
  type RunDepartmentInfo,
  getRerun,
  stopRun,
  clearRunLogs,
  type RunPage,
  type RunFilters,
} from "@/api/runs";
import { getApiError } from "@/api/errors";
import { RUN_RESULT_LABELS } from "@/app/runLabels";
import { formatDateTime } from "@/app/formatters";
import { useSessionStore } from "@/stores/sessionStore";
const ARR_HEADER = [
  { title: "Schedule", key: "schedule_name" },
  { title: "Project", key: "project_name" },
  { title: "Version", key: "project_version" },
  { title: "Executor", key: "executor_name" },
  { title: "Started At", key: "started_at" },
  { title: "Ended At", key: "ended_at" },
  { title: "Status", key: "result" },
  { title: "Actions", key: "actions" },
];
const sessionStore = useSessionStore();
const route = useRoute();
const router = useRouter();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
function emptyFilters(): RunFilters {
  return {
    departmentIds: [],
    projectName: "",
    scheduleName: "",
    results: [],
    executorId: "",
    startedFrom: "",
    startedUntil: "",
  };
}
const arrDepartment = ref<RunDepartmentInfo[]>([]);
const filters = ref(emptyFilters());
const initialResult = ARR_RUN_RESULT.find((result) => result === route.query.result);
if (initialResult) filters.value.results = [initialResult];
if (typeof route.query.department_id === "string")
  filters.value.departmentIds = [route.query.department_id];
let appliedFilters = {
  ...filters.value,
  departmentIds: [...filters.value.departmentIds],
  results: [...filters.value.results],
};
const page = shallowRef<RunPage | null>(null);
const boolLoading = ref(false);
const strError = ref("");
const arrSelectedId = ref<string[]>([]);
const arrConfirmedId = ref<string[]>([]);
const boolSelecting = ref(false);
const boolClearDialog = ref(false);
const boolClearing = ref(false);
const strClearError = ref("");
const clearResult = ref<Awaited<ReturnType<typeof clearRunLogs>> | null>(null);
const boolActionBusy = ref(false);
const rerunInfo = ref<Awaited<ReturnType<typeof getRerun>> | null>(null);
let intLoadRevision = 0;
let intSelectionRevision = 0;
function updateSelection(ids: string[]): void {
  intSelectionRevision += 1;
  boolSelecting.value = false;
  arrSelectedId.value = ids;
}
function clearSelection(): void {
  updateSelection([]);
}
async function load(pageNumber = page.value?.page ?? 1): Promise<void> {
  const intRevision = ++intLoadRevision;
  boolLoading.value = true;
  strError.value = "";
  try {
    const response = await getRuns(appliedFilters, pageNumber);
    if (intRevision === intLoadRevision) page.value = response;
  } catch (e) {
    if (intRevision === intLoadRevision) strError.value = getApiError(e).message;
  } finally {
    if (intRevision === intLoadRevision) boolLoading.value = false;
  }
}
function apply(): void {
  appliedFilters = {
    ...filters.value,
    departmentIds: [...filters.value.departmentIds],
    results: [...filters.value.results],
  };
  clearSelection();
  page.value = null;
  void load(1);
}
function clearFilters(): void {
  filters.value = emptyFilters();
  apply();
}
async function selectAll(): Promise<void> {
  if (boolSelecting.value || boolLoading.value || boolClearDialog.value) return;
  const intRevision = ++intSelectionRevision;
  // Applying filters replaces this detached snapshot instead of mutating it.
  const selectionFilters = appliedFilters;
  boolSelecting.value = true;
  strError.value = "";
  try {
    const arrId = await getMatchingRunIds(selectionFilters);
    if (intRevision === intSelectionRevision) arrSelectedId.value = arrId;
  } catch (e) {
    if (intRevision === intSelectionRevision) strError.value = getApiError(e).message;
  } finally {
    if (intRevision === intSelectionRevision) boolSelecting.value = false;
  }
}
function confirmClear(): void {
  if (
    !arrSelectedId.value.length ||
    boolSelecting.value ||
    boolLoading.value ||
    boolClearDialog.value
  )
    return;
  arrConfirmedId.value = [...arrSelectedId.value];
  strClearError.value = "";
  boolClearDialog.value = true;
}
async function clearLogs(): Promise<void> {
  if (boolClearing.value || !boolClearDialog.value || !arrConfirmedId.value.length) return;
  const arrRunId = [...arrConfirmedId.value];
  boolClearing.value = true;
  strClearError.value = "";
  try {
    clearResult.value = await clearRunLogs(arrRunId);
    boolClearDialog.value = false;
    clearSelection();
  } catch (e) {
    strClearError.value = getApiError(e).message;
  } finally {
    boolClearing.value = false;
  }
}
async function rerun(id: string): Promise<void> {
  if (boolActionBusy.value) return;
  boolActionBusy.value = true;
  strError.value = "";
  try {
    rerunInfo.value = await getRerun(id);
  } catch (e) {
    strError.value = getApiError(e).message;
  } finally {
    boolActionBusy.value = false;
  }
}
async function stop(id: string): Promise<void> {
  boolActionBusy.value = true;
  strError.value = "";
  try {
    await stopRun(id);
    await load();
  } catch (e) {
    strError.value = getApiError(e).message;
  } finally {
    boolActionBusy.value = false;
  }
}
function runCreated(): void {
  rerunInfo.value = null;
  void router.push({ name: "job-queue" });
}
onBeforeUnmount(() => {
  intLoadRevision += 1;
  clearSelection();
});
onMounted(async () => {
  void load();
  try {
    arrDepartment.value = await getRunDepartments();
  } catch (e) {
    strError.value = getApiError(e).message;
  }
});
</script>
<style scoped></style>
