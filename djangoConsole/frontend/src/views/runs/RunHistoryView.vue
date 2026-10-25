<!-- FileName: RunHistoryView.vue -->
<template>
  <div class="d-flex align-center flex-wrap ga-3 mb-4">
    <h1 class="text-h5">Run History</h1>
    <v-spacer />
    <v-btn
      variant="tonal"
      prepend-icon="mdi-refresh"
      :loading="boolLoading"
      @click="load()">
      Refresh
    </v-btn>
  </div>

  <v-card variant="elevated" class="mb-4">
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
              variant="underlined"
              multiple
              chips
              hide-details />
          </v-col>

          <v-col cols="12" md="4">
            <v-text-field
              v-model="filters.scheduleName"
              label="Schedule"
              variant="underlined"
              hide-details />
          </v-col>

          <v-col cols="12" md="4">
            <v-text-field
              v-model="filters.projectName"
              label="Project"
              variant="underlined"
              hide-details />
          </v-col>

          <v-col cols="12" md="4">
            <v-select
              v-model="filters.statuses"
              :items="
                ARR_RUN_STATUS.map((value) => ({ value, title: RUN_STATUS_LABELS[value] }))
              "
              label="Status"
              variant="underlined"
              multiple
              chips
              hide-details />
          </v-col>

          <v-col cols="12" md="4">
            <v-text-field
              v-model="filters.startedFrom"
              type="datetime-local"
              step="1"
              label="Started From"
              variant="underlined" />
          </v-col>

          <v-col cols="12" md="4">
            <v-text-field
              v-model="filters.startedUntil"
              type="datetime-local"
              step="1"
              label="Started Before"
              variant="underlined" />
          </v-col>
        </v-row>

        <div class="d-flex ga-2 mt-4">
          <v-btn
            variant="tonal"
            prepend-icon="mdi-filter-remove-outline"
            @click="clearFilters">
            Reset Filters
          </v-btn>
          <v-spacer />
          <v-btn type="submit" color="primary" variant="tonal" prepend-icon="mdi-check">
            Apply
          </v-btn>
        </div>
      </form>
    </v-card-text>
  </v-card>

  <v-alert v-if="strError" type="error" variant="tonal" class="mb-4">
    {{ strError }}
  </v-alert>

  <v-alert v-if="clearResult" type="info" variant="tonal" class="mb-4">
    <p>
      Cleared:
      <span class="font-weight-bold">{{ clearResult.cleared }}</span>
      · Skipped:
      <span class="font-weight-bold">{{ clearResult.skipped.length }}</span>
      · Failed:
      <span class="font-weight-bold">{{ clearResult.failed.length }}</span>
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
      prepend-icon="mdi-select-all"
      :disabled="!page?.total_count || boolSelecting || boolLoading"
      :loading="boolSelecting"
      @click="selectAll">
      Select All Matching Runs
    </v-btn>

    <v-btn
      size="small"
      variant="tonal"
      prepend-icon="mdi-selection-remove"
      :disabled="!arrSelectedId.length && !boolSelecting"
      @click="clearSelection">
      Clear Selection
    </v-btn>
    <v-spacer />
    <v-btn
      color="warning"
      variant="tonal"
      prepend-icon="mdi-delete-outline"
      :disabled="!arrSelectedId.length || boolSelecting || boolLoading || boolClearing"
      @click="confirmClear">
      Clear Logs
    </v-btn>
  </div>

  <TimeZoneHint :time-zone="strTimeZone" :updated-at="strUpdatedAt" />

  <v-card variant="outlined">
    <v-data-table-server
      :model-value="arrSelectedId"
      :headers="ARR_HEADER"
      :items="page?.runs ?? []"
      :items-length="page?.total_count ?? 0"
      :items-per-page="page?.page_size ?? INT_LIST_PAGE_SIZE"
      :loading="boolLoading"
      item-value="id"
      show-select
      select-strategy="page"
      disable-sort
      hide-default-footer
      @update:model-value="updateSelection">
      <template #item.schedule_name="{ item }">{{ item.schedule_name || "—" }}</template>

      <template #item.started_at="{ item }">
        {{ formatDateTime(item.started_at, strTimeZone, false) }}
      </template>

      <template #item.ended_at="{ item }">
        {{ formatRunEndTime(item, strTimeZone, false) }}
      </template>

      <template #item.status="{ item }">
        <v-chip
          :border="`${RUN_STATUS_COLORS[item.status]} thin opacity-25`"
          :color="RUN_STATUS_COLORS[item.status]"
          :text="RUN_STATUS_LABELS[item.status]"
          variant="text"
          size="x-small" />
      </template>

      <template #item.actions="{ item }">
        <div class="d-flex align-center ga-1">
          <v-btn
            v-tooltip:bottom="'View Run Details'"
            :to="{
              name: 'run-details',
              params: { runId: item.id },
              query: { ...route.query, from: 'run-history' },
            }"
            size="small"
            variant="text"
            aria-label="View Run Details"
            icon="mdi-eye-outline" />

          <v-btn
            v-tooltip:bottom="'Run Most Recently Uploaded Version'"
            size="small"
            variant="text"
            :disabled="boolActionBusy || !item.can_rerun"
            aria-label="Rerun"
            icon="mdi-replay"
            @click="rerun(item.id)" />

          <v-btn
            v-if="item.can_stop"
            v-tooltip:bottom="'Stop Run'"
            size="small"
            color="warning"
            variant="text"
            :disabled="boolActionBusy"
            aria-label="Stop Run"
            icon="mdi-stop-circle-outline"
            @click="stop(item.id)" />

          <span v-if="item.stop_requested" class="text-body-2">Stop requested</span>
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
        @update:model-value="changePage" />
    </div>
  </v-card>

  <v-dialog v-model="boolClearDialog" :persistent="boolClearing" max-width="640">
    <v-card>
      <v-card-title>Clear Logs</v-card-title>

      <v-card-text>
        <p>
          Clear logs from Console for
          <span class="font-weight-bold">{{ arrConfirmedId.length }}</span>
          selected runs? Run summaries, inputs, outputs and files on Executors are retained.
          Protected runs are skipped.
        </p>

        <v-alert v-if="strClearError" type="error" variant="tonal" class="mt-4">
          {{ strClearError }}
        </v-alert>
      </v-card-text>

      <v-card-actions>
        <v-btn
          variant="tonal"
          prepend-icon="mdi-close"
          :disabled="boolClearing"
          @click="boolClearDialog = false">
          Cancel
        </v-btn>
        <v-spacer />
        <v-btn
          variant="tonal"
          prepend-icon="mdi-delete-outline"
          color="warning"
          :loading="boolClearing"
          @click="clearLogs">
          Clear Logs
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <PackageRunDialog
    v-if="rerunInfo"
    :package-id="rerunInfo.package_id"
    :executor-ids="rerunInfo.executor_ids"
    :group-id="rerunInfo.group_id"
    :original-job-active="rerunInfo.original_job_active"
    @close="rerunInfo = null"
    @view-job-queue="viewJobQueue" />
</template>

<script setup lang="ts">
import { shallowRef, computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import TimeZoneHint from "@/components/common/TimeZoneHint.vue";
import PackageRunDialog from "@/components/packages/PackageRunDialog.vue";

import {
  ARR_RUN_STATUS,
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
import { INT_LIST_PAGE_SIZE } from "@/api/generated/browserApi";

import { RUN_STATUS_LABELS, RUN_STATUS_COLORS } from "@/app/runLabels";
import { formatDateTime, formatRunEndTime } from "@/app/formatters";

import { useSessionStore } from "@/stores/sessionStore";

const ARR_HEADER = [
  { title: "Schedule", key: "schedule_name" },
  { title: "Project Name", key: "project_name" },
  { title: "Project Version", key: "project_version" },
  { title: "Executor", key: "executor_name" },
  { title: "Started At", key: "started_at" },
  { title: "Ended At", key: "ended_at" },
  { title: "Status", key: "status" },
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
    statuses: [],
    executorId: "",
    startedFrom: "",
    startedUntil: "",
  };
}

const arrDepartment = ref<RunDepartmentInfo[]>([]);
const filters = ref(emptyFilters());
const appliedFilters = computed<RunFilters>(() => {
  function getQueryText(key: string): string {
    const value = route.query[key];
    return typeof value === "string" ? value : "";
  }

  return {
    departmentIds: [route.query.department_id]
      .flat()
      .filter((value): value is string => typeof value === "string"),
    projectName: getQueryText("project_name"),
    scheduleName: getQueryText("schedule_name"),
    statuses: ARR_RUN_STATUS.filter((status) =>
      [route.query.status].flat().includes(status),
    ),
    executorId: getQueryText("executor_id"),
    startedFrom: getQueryText("started_from"),
    startedUntil: getQueryText("started_until"),
  };
});

const page = shallowRef<RunPage | null>(null);
const strUpdatedAt = ref<string | null>(null);
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

async function load(): Promise<void> {
  const intRevision = ++intLoadRevision;
  boolLoading.value = true;
  strError.value = "";
  try {
    const response = await getRuns(appliedFilters.value, Number(route.query.page) || 1);
    if (intRevision === intLoadRevision) {
      page.value = response;
      strUpdatedAt.value = new Date().toISOString();
    }
  } catch (e) {
    if (intRevision === intLoadRevision) strError.value = getApiError(e).message;
  } finally {
    if (intRevision === intLoadRevision) boolLoading.value = false;
  }
}

async function changePage(value: number): Promise<void> {
  await router.replace({ query: { ...route.query, page: String(value) } });
}

async function apply(): Promise<void> {
  const location = {
    name: "run-history",
    query: {
      department_id: filters.value.departmentIds,
      project_name: filters.value.projectName.trim() || undefined,
      schedule_name: filters.value.scheduleName.trim() || undefined,
      status: filters.value.statuses,
      executor_id: filters.value.executorId || undefined,
      started_from: filters.value.startedFrom || undefined,
      started_until: filters.value.startedUntil || undefined,
    },
  };
  clearSelection();
  if (router.resolve(location).fullPath === route.fullPath) {
    page.value = null;
    strUpdatedAt.value = null;
    await load();
  } else await router.replace(location);
}

function clearFilters(): void {
  filters.value = emptyFilters();
  void apply();
}

async function selectAll(): Promise<void> {
  if (boolSelecting.value || boolLoading.value || boolClearDialog.value) return;
  const intRevision = ++intSelectionRevision;
  // Query changes replace this snapshot instead of mutating it.
  const selectionFilters = appliedFilters.value;
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

function viewJobQueue(): void {
  rerunInfo.value = null;
  void router.push({ name: "job-queue" });
}

onBeforeUnmount(() => {
  intLoadRevision += 1;
  clearSelection();
});

watch(
  [appliedFilters, () => route.query.page],
  ([currentFilters], [previousFilters]) => {
    if (route.name !== "run-history") return;
    if (JSON.stringify(currentFilters) !== JSON.stringify(previousFilters)) {
      filters.value = {
        ...currentFilters,
        departmentIds: [...currentFilters.departmentIds],
        statuses: [...currentFilters.statuses],
      };
      clearSelection();
    }
    page.value = null;
    strUpdatedAt.value = null;
    void load();
  },
  { immediate: true },
);

onMounted(async () => {
  try {
    arrDepartment.value = await getRunDepartments();
  } catch (e) {
    strError.value = getApiError(e).message;
  }
});
</script>

<style scoped></style>
