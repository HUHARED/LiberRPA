<!-- FileName: CurrentRunsView.vue -->
<template>
  <div class="d-flex align-center flex-wrap ga-3 mb-4">
    <h2 class="text-h6">Current Runs</h2>
    <v-spacer />
    <v-switch
      v-model="boolAutoRefresh"
      label="Auto Refresh"
      true-icon="mdi-sync"
      color="primary"
      density="compact"
      hide-details />

    <v-btn
      variant="tonal"
      prepend-icon="mdi-refresh"
      :loading="boolLoading"
      :disabled="boolLoading"
      @click="load()">
      Refresh
    </v-btn>
  </div>

  <v-card variant="elevated" class="mb-4">
    <v-card-text>
      <form @submit.prevent="apply">
        <v-row>
          <v-col cols="12" md="6">
            <v-select
              v-model="filters.departmentIds"
              :items="arrDepartment ?? []"
              :item-title="
                (department: RunDepartmentInfo) =>
                  `${department.path}${department.deleted_at ? ' (Archived)' : ''}`
              "
              item-value="id"
              label="Department"
              variant="underlined"
              :disabled="boolLoading"
              multiple
              chips
              hide-details />
          </v-col>

          <v-col cols="12" md="6">
            <v-text-field
              v-model="filters.projectName"
              label="Project"
              variant="underlined"
              maxlength="128"
              :disabled="boolLoading"
              hide-details />
          </v-col>
        </v-row>

        <div class="d-flex ga-2 mt-4">
          <v-btn
            variant="tonal"
            prepend-icon="mdi-filter-remove-outline"
            :disabled="boolLoading"
            @click="clearFilters">
            Reset Filters
          </v-btn>
          <v-spacer />
          <v-btn
            type="submit"
            color="primary"
            variant="tonal"
            prepend-icon="mdi-check"
            :disabled="boolLoading">
            Apply
          </v-btn>
        </div>
      </form>
    </v-card-text>
  </v-card>

  <v-alert v-if="strError" type="error" variant="tonal" class="mb-4">
    {{ strError }}
  </v-alert>

  <v-progress-linear v-if="boolLoading" indeterminate color="primary" class="mb-4" />

  <template v-if="page">
    <p class="text-body-2 text-medium-emphasis mb-3">
      Updated At: {{ formatDateTime(page.updated_at, strTimeZone) }}
    </p>

    <v-card variant="outlined">
      <v-data-table-server
        :headers="ARR_HEADER"
        :items="page.runs"
        :items-length="page.total_count"
        :items-per-page="page.page_size"
        item-value="id"
        disable-sort
        hide-default-footer>
        <template #item.started_at="{ item }">
          {{ formatDateTime(item.started_at, strTimeZone) }}
        </template>

        <template #item.elapsed="{ item }">
          {{
            formatDuration(
              (Date.parse(page.updated_at) - Date.parse(item.started_at)) / 1000,
            )
          }}
        </template>

        <template #no-data>No current runs match the filters.</template>
      </v-data-table-server>

      <v-divider />

      <div class="d-flex align-center justify-space-between pa-3">
        <span>{{ page.total_count }} runs</span>
        <v-pagination
          v-if="page.total_pages > 1"
          :model-value="page.page"
          :length="page.total_pages"
          :total-visible="5"
          :disabled="boolLoading"
          @update:model-value="load" />
      </div>
    </v-card>
  </template>
</template>

<script setup lang="ts">
import {
  computed,
  onActivated,
  onBeforeUnmount,
  onDeactivated,
  onMounted,
  ref,
  shallowRef,
  watch,
} from "vue";

import { getCurrentRuns, type OverviewFilters } from "@/api/overview";
import { getRunDepartments, type RunDepartmentInfo } from "@/api/runs";
import { getApiError } from "@/api/errors";
import type { CurrentRunListResponse } from "@/api/generated/browserApi";

import { formatDateTime, formatDuration } from "@/app/formatters";
import { useSessionStore } from "@/stores/sessionStore";
import { useRetryDelay } from "@/composables/useRetryDelay";

const ARR_HEADER = [
  { title: "Project", key: "project_name" },
  { title: "Version", key: "project_version" },
  { title: "Executor", key: "executor_name" },
  { title: "Started At", key: "started_at" },
  { title: "Elapsed", key: "elapsed" },
];
const INT_REFRESH_INTERVAL_MS = 60_000;

const sessionStore = useSessionStore();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");

const arrDepartment = shallowRef<RunDepartmentInfo[] | null>(null);
const filters = ref<OverviewFilters>({ departmentIds: [], projectName: "" });
let appliedFilters: OverviewFilters = { departmentIds: [], projectName: "" };

const page = shallowRef<CurrentRunListResponse | null>(null);
const boolLoading = ref(false);
const strError = ref("");
const { intRetrySeconds, setRetryDelay } = useRetryDelay();
const boolAutoRefresh = ref(false);
let intLoadRevision = 0;
let intCurrentPage = 1;
let boolActive = false;
let intRefreshTimer: ReturnType<typeof setInterval> | undefined;

async function load(pageNumber = intCurrentPage): Promise<void> {
  if (boolLoading.value) return;
  const intRevision = ++intLoadRevision;
  intCurrentPage = pageNumber;
  boolLoading.value = true;
  strError.value = "";
  page.value = null;
  try {
    const [response, departments] = await Promise.all([
      getCurrentRuns(appliedFilters, pageNumber),
      arrDepartment.value === null ? getRunDepartments() : arrDepartment.value,
    ]);
    if (intRevision !== intLoadRevision) return;
    page.value = response;
    intCurrentPage = response.page;
    arrDepartment.value = departments;
    setRetryDelay(0);
  } catch (e) {
    if (intRevision === intLoadRevision) {
      const error = getApiError(e);
      strError.value = error.message;
      if (error.statusCode === 429 && (error.retryAfterSeconds ?? 0) > 0)
        setRetryDelay(error.retryAfterSeconds);
    }
  } finally {
    if (intRevision === intLoadRevision) boolLoading.value = false;
  }
}

function apply(): void {
  if (boolLoading.value) return;
  appliedFilters = {
    departmentIds: [...filters.value.departmentIds],
    projectName: filters.value.projectName.trim(),
  };
  void load(1);
}

function clearFilters(): void {
  filters.value = { departmentIds: [], projectName: "" };
  apply();
}

function updateRefreshTimer(): void {
  clearInterval(intRefreshTimer);
  intRefreshTimer = undefined;
  if (!boolActive || !boolAutoRefresh.value || document.visibilityState !== "visible")
    return;
  intRefreshTimer = setInterval(() => {
    if (intRetrySeconds.value === 0) void load();
  }, INT_REFRESH_INTERVAL_MS);
}

watch(boolAutoRefresh, updateRefreshTimer);

onMounted(() => {
  document.addEventListener("visibilitychange", updateRefreshTimer);
});

onActivated(() => {
  boolActive = true;
  updateRefreshTimer();
  if (intRetrySeconds.value === 0) void load();
});

onDeactivated(() => {
  boolActive = false;
  intLoadRevision += 1;
  boolLoading.value = false;
  updateRefreshTimer();
});

onBeforeUnmount(() => {
  intLoadRevision += 1;
  clearInterval(intRefreshTimer);
  document.removeEventListener("visibilitychange", updateRefreshTimer);
});
</script>

<style scoped></style>
