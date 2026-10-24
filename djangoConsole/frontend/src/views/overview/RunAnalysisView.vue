<!-- FileName: RunAnalysisView.vue -->
<template>
  <div class="d-flex align-center flex-wrap ga-3 mb-4">
    <h2 class="text-h6">Run Analysis</h2>
    <v-spacer />
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

          <v-col cols="12" md="4">
            <v-select
              v-model="dateRange"
              :items="ARR_DATE_RANGE_OPTION"
              label="Date Range"
              variant="underlined"
              :disabled="boolLoading"
              hide-details />
          </v-col>

          <v-col cols="12" md="4">
            <v-text-field
              v-model="filters.dateFrom"
              label="Ended From"
              :variant="dateRange === DateRange.Custom ? 'underlined' : 'plain'"
              type="date"
              :max="filters.dateUntil || undefined"
              :readonly="dateRange !== DateRange.Custom"
              :disabled="boolLoading"
              :hint="strTimeZone"
              persistent-hint
              required />
          </v-col>

          <v-col cols="12" md="4">
            <v-text-field
              v-model="filters.dateUntil"
              label="Ended Through"
              :variant="dateRange === DateRange.Custom ? 'underlined' : 'plain'"
              type="date"
              :min="filters.dateFrom || undefined"
              :readonly="dateRange !== DateRange.Custom"
              :disabled="boolLoading"
              :hint="strTimeZone"
              persistent-hint
              required />
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

  <p class="text-body-2 text-medium-emphasis mb-4">
    Statistics use retained run records. Deleted records are not included.
  </p>

  <v-alert v-if="strError" type="error" variant="tonal" class="mb-4">
    {{ strError }}
  </v-alert>

  <v-progress-linear v-if="boolLoading" indeterminate color="primary" class="mb-4" />

  <template v-if="statistics">
    <p class="text-body-2 text-medium-emphasis mb-3">
      {{ statistics.date_from }} – {{ statistics.date_until }} ·
      {{ statistics.time_zone }} · Updated At:
      {{ formatDateTime(statistics.updated_at, statistics.time_zone, false) }}
    </p>

    <div class="d-flex flex-wrap ga-6 mb-4">
      <p>
        Total Runs:
        <strong>{{ statistics.total_count }}</strong>
      </p>
      <p>
        Total Run Time:
        <strong>{{ formatDuration(statistics.total_duration_seconds) }}</strong>
      </p>
    </div>

    <v-card variant="outlined" class="mb-4">
      <v-table>
        <thead>
          <tr>
            <th scope="col">Result</th>
            <th scope="col" class="text-end">Runs</th>
            <th scope="col" class="text-end">Percentage</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="result in statistics.results" :key="result.status">
            <td>{{ RUN_STATUS_LABELS[result.status] }}</td>
            <td class="text-end">{{ result.count }}</td>
            <td class="text-end">
              {{
                statistics.total_count
                  ? `${((result.count / statistics.total_count) * 100).toFixed(2)}%`
                  : "—"
              }}
            </td>
          </tr>
        </tbody>
      </v-table>
    </v-card>

    <v-card variant="outlined" class="mb-4">
      <v-card-title>Daily Runs</v-card-title>

      <v-card-text>
        <v-sheet
          v-if="statistics.total_count"
          height="280"
          color="transparent"
          class="position-relative">
          <Bar
            :data="chartData"
            :options="chartOptions"
            aria-label="Daily run counts by result" />
        </v-sheet>
        <p v-else class="text-medium-emphasis">No ended runs match the filters.</p>
      </v-card-text>
    </v-card>

    <v-card variant="outlined">
      <v-card-title>Runs by Executor</v-card-title>

      <v-data-table-server
        :headers="ARR_EXECUTOR_HEADER"
        :items="arrExecutorRow"
        :items-length="statistics.executors.total_count"
        :items-per-page="statistics.executors.page_size"
        item-value="id"
        disable-sort
        hide-default-footer>
        <template #item.duration_seconds="{ item }">
          {{ formatDuration(item.duration_seconds) }}
        </template>

        <template #no-data>No ended runs match the filters.</template>
      </v-data-table-server>

      <v-divider />

      <div class="d-flex align-center justify-space-between pa-3">
        <span>{{ statistics.executors.total_count }} executors</span>
        <v-pagination
          v-if="statistics.executors.total_pages > 1"
          :model-value="statistics.executors.page"
          :length="statistics.executors.total_pages"
          :total-visible="5"
          :disabled="boolLoading"
          @update:model-value="load" />
      </div>
    </v-card>
  </template>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";
import { useTheme } from "vuetify";
import { Bar } from "vue-chartjs";
import {
  Chart as ChartJS,
  BarElement,
  CategoryScale,
  LinearScale,
  Legend,
  type ChartData,
  type ChartOptions,
} from "chart.js";

import { getRunStatistics, type RunStatisticsFilters } from "@/api/overview";
import { getRunDepartments, type RunDepartmentInfo } from "@/api/runs";
import { getApiError } from "@/api/errors";
import {
  RunStatus,
  INT_MAX_RUN_STATISTICS_DAYS,
  type RunStatisticsResponse,
} from "@/api/generated/browserApi";

import { RUN_STATUS_LABELS, RUN_STATUS_COLORS } from "@/app/runLabels";
import { formatDateTime, formatDateTimeInput, formatDuration } from "@/app/formatters";

import { useSessionStore } from "@/stores/sessionStore";

ChartJS.register(BarElement, CategoryScale, LinearScale, Legend);

enum DateRange {
  Today = "today",
  Last7Days = "last_7_days",
  Last30Days = "last_30_days",
  Custom = "custom",
}
const ARR_DATE_RANGE_OPTION = [
  { value: DateRange.Today, title: "Today" },
  { value: DateRange.Last7Days, title: "Last 7 Days" },
  { value: DateRange.Last30Days, title: "Last 30 Days" },
  { value: DateRange.Custom, title: "Custom" },
];
const ARR_ENDED_STATUS = Object.values(RunStatus).filter(
  (status) => status !== RunStatus.Running,
);
const ARR_EXECUTOR_HEADER = [
  { title: "Executor", key: "name" },
  { title: "Total", key: "total_count", align: "end" as const },
  ...ARR_ENDED_STATUS.map((status) => ({
    title: RUN_STATUS_LABELS[status],
    key: status,
    align: "end" as const,
  })),
  { title: "Run Time", key: "duration_seconds", align: "end" as const },
];
const INT_DAY_MS = 86_400_000;

const sessionStore = useSessionStore();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const theme = useTheme();

const arrDepartment = shallowRef<RunDepartmentInfo[] | null>(null);
const dateRange = ref(DateRange.Last7Days);
const filters = ref<RunStatisticsFilters>({
  departmentIds: [],
  projectName: "",
  dateFrom: "",
  dateUntil: "",
});
let appliedFilters: RunStatisticsFilters;

const statistics = shallowRef<RunStatisticsResponse | null>(null);
const boolLoading = ref(false);
const strError = ref("");
let intLoadRevision = 0;
let intExecutorPage = 1;

const arrExecutorRow = computed(() =>
  (statistics.value?.executors.entries ?? []).map((executor) => ({
    ...executor,
    ...Object.fromEntries(executor.results.map((result) => [result.status, result.count])),
  })),
);

const chartData = computed<ChartData<"bar">>(() => {
  const response = statistics.value;
  const arrDate: string[] = [];
  if (response) {
    const intLastDate = Date.parse(response.date_until);
    for (
      let intDate = Date.parse(response.date_from);
      intDate <= intLastDate;
      intDate += INT_DAY_MS
    )
      arrDate.push(new Date(intDate).toISOString().slice(0, 10));
  }
  const mapDailyResult = new Map(
    response?.daily.map((day) => [
      day.date,
      new Map(day.results.map((result) => [result.status, result.count])),
    ]),
  );
  return {
    labels: arrDate,
    datasets: ARR_ENDED_STATUS.map((status) => ({
      label: RUN_STATUS_LABELS[status],
      data: arrDate.map((strDate) => mapDailyResult.get(strDate)?.get(status) ?? 0),
      backgroundColor: theme.current.value.colors[RUN_STATUS_COLORS[status]],
    })),
  };
});

const chartOptions = computed<ChartOptions<"bar">>(() => {
  const strTextColor = theme.current.value.colors["on-surface"];
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    events: [],
    plugins: {
      legend: { labels: { color: strTextColor }, onClick: () => {} },
    },
    scales: {
      x: { stacked: true, ticks: { color: strTextColor }, grid: { display: false } },
      y: {
        stacked: true,
        beginAtZero: true,
        ticks: { precision: 0, color: strTextColor },
        grid: { color: theme.current.value.colors["surface-variant"] },
      },
    },
  };
});

function updatePresetDates(): void {
  if (dateRange.value === DateRange.Custom) return;
  const strToday = formatDateTimeInput(new Date().toISOString(), strTimeZone.value).slice(
    0,
    10,
  );
  const intDays =
    dateRange.value === DateRange.Today
      ? 1
      : dateRange.value === DateRange.Last7Days
        ? 7
        : 30;
  filters.value.dateFrom = new Date(Date.parse(strToday) - (intDays - 1) * INT_DAY_MS)
    .toISOString()
    .slice(0, 10);
  filters.value.dateUntil = strToday;
}

async function load(executorPage = intExecutorPage): Promise<void> {
  if (boolLoading.value) return;
  const intRevision = ++intLoadRevision;
  intExecutorPage = executorPage;
  boolLoading.value = true;
  strError.value = "";
  statistics.value = null;
  try {
    const [response, departments] = await Promise.all([
      getRunStatistics(appliedFilters, executorPage),
      arrDepartment.value === null ? getRunDepartments() : arrDepartment.value,
    ]);
    if (intRevision !== intLoadRevision) return;
    statistics.value = response;
    intExecutorPage = response.executors.page;
    arrDepartment.value = departments;
  } catch (e) {
    if (intRevision === intLoadRevision) strError.value = getApiError(e).message;
  } finally {
    if (intRevision === intLoadRevision) boolLoading.value = false;
  }
}

function apply(): void {
  if (boolLoading.value) return;
  updatePresetDates();
  const intDays =
    (Date.parse(filters.value.dateUntil) - Date.parse(filters.value.dateFrom)) /
      INT_DAY_MS +
    1;
  if (!Number.isFinite(intDays) || intDays < 1 || intDays > INT_MAX_RUN_STATISTICS_DAYS) {
    statistics.value = null;
    strError.value = `Choose a date range of 1 to ${INT_MAX_RUN_STATISTICS_DAYS} days.`;
    return;
  }
  appliedFilters = {
    ...filters.value,
    departmentIds: [...filters.value.departmentIds],
    projectName: filters.value.projectName.trim(),
  };
  void load(1);
}

function clearFilters(): void {
  dateRange.value = DateRange.Last7Days;
  filters.value = { departmentIds: [], projectName: "", dateFrom: "", dateUntil: "" };
  apply();
}

watch(dateRange, updatePresetDates);

onMounted(apply);

onBeforeUnmount(() => {
  intLoadRevision += 1;
});
</script>

<style scoped></style>
