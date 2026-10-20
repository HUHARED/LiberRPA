<!-- FileName: InstanceOverviewView.vue -->
<template>
  <div class="d-flex align-center justify-space-between ga-4 mb-4">
    <h2 class="text-h6">Overview</h2>

    <v-btn
      variant="tonal"
      prepend-icon="mdi-refresh"
      :loading="boolLoading"
      @click="loadOverview">
      Refresh
    </v-btn>
  </div>

  <v-alert v-if="accessError" type="error" variant="tonal" class="mb-4" role="alert">
    {{ accessError.message }}
  </v-alert>

  <v-progress-linear v-if="boolSummaryLoading" indeterminate class="mb-4" />

  <v-alert v-if="summaryError" type="error" variant="tonal" class="mb-4" role="alert">
    {{ summaryError.message }}
    <p v-if="instanceSummary" class="mt-2">
      Previously loaded component and disk information is shown and may be out of date.
    </p>
  </v-alert>

  <template v-if="instanceSummary">
    <p class="text-body-2 mb-2">Version: {{ instanceSummary.version }}</p>
    <p class="text-body-2 mb-2">
      Service State:
      {{
        instanceSummary.service_state === null
          ? "Unknown"
          : MAP_SERVICE_STATE_LABEL[instanceSummary.service_state]
      }}
    </p>
    <p v-if="instanceSummary.maintenance_entered_at" class="text-body-2 mb-2">
      Maintenance Entered At:
      {{
        formatDateTime(instanceSummary.maintenance_entered_at, instanceSummary.time_zone)
      }}
    </p>
    <p class="text-body-2 mb-2">Instance Time Zone: {{ instanceSummary.time_zone }}</p>
    <p class="text-body-2 text-medium-emphasis mb-4">
      Updated at {{ formatDateTime(instanceSummary.updated_at, instanceSummary.time_zone) }}
    </p>

    <h3 class="text-h6 mb-2">Components</h3>
    <v-table class="mb-4" :aria-busy="boolSummaryLoading">
      <thead>
        <tr>
          <th scope="col">Component</th>
          <th scope="col">Status</th>
          <th scope="col">Checked At</th>
          <th scope="col">Message</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="component in instanceSummary.components" :key="component.component">
          <th scope="row">{{ MAP_COMPONENT_LABEL[component.component] }}</th>
          <td>
            <v-chip
              :color="MAP_STATUS_COLOR[component.status]"
              size="small"
              variant="tonal">
              {{ MAP_STATUS_LABEL[component.status] }}
            </v-chip>
          </td>
          <td class="text-no-wrap">
            {{ formatDateTime(component.checked_at, instanceSummary.time_zone) }}
          </td>
          <td>{{ component.message }}</td>
        </tr>
      </tbody>
    </v-table>

    <h3 class="text-h6 mb-2">Disk Space</h3>
    <p class="text-body-2 text-medium-emphasis mb-2">
      Disk containing Console file storage. Checked at
      {{ formatDateTime(instanceSummary.storage.checked_at, instanceSummary.time_zone) }}
    </p>
    <v-table class="mb-2" :aria-busy="boolSummaryLoading">
      <thead>
        <tr>
          <th scope="col">Storage</th>
          <th scope="col">Total</th>
          <th scope="col">Used</th>
          <th scope="col">Free</th>
          <th scope="col">Status</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th scope="row">File Storage</th>
          <td class="text-no-wrap">
            {{ formatStorageBytes(instanceSummary.storage.total_bytes) }}
          </td>
          <td class="text-no-wrap">
            {{ formatStorageBytes(instanceSummary.storage.used_bytes) }}
          </td>
          <td class="text-no-wrap">
            {{ formatStorageBytes(instanceSummary.storage.free_bytes) }}
          </td>
          <td>
            <v-chip
              :color="MAP_STATUS_COLOR[instanceSummary.storage.status]"
              size="small"
              variant="tonal">
              {{ MAP_STATUS_LABEL[instanceSummary.storage.status] }}
            </v-chip>
          </td>
        </tr>
      </tbody>
    </v-table>
    <p class="text-body-2 mb-6">{{ instanceSummary.storage.message }}</p>

    <h3 class="text-h6 mb-2">Last Successful Backup</h3>
    <v-table v-if="instanceSummary.last_successful_backup" class="mb-6">
      <thead>
        <tr>
          <th scope="col">Completed At</th>
          <th scope="col">Data As Of</th>
          <th scope="col">Size</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td class="text-no-wrap">
            {{
              formatDateTime(
                instanceSummary.last_successful_backup.ended_at,
                instanceSummary.time_zone,
              )
            }}
          </td>
          <td class="text-no-wrap">
            {{
              formatDateTime(
                instanceSummary.last_successful_backup.data_as_of,
                instanceSummary.time_zone,
              )
            }}
          </td>
          <td class="text-no-wrap">
            {{ formatFileSize(instanceSummary.last_successful_backup.size_bytes) }}
          </td>
        </tr>
      </tbody>
    </v-table>
    <p v-else class="text-body-2 text-medium-emphasis mb-6">
      No successful backup information is available.
    </p>
  </template>

  <h3 class="text-h6 mb-3">Host Monitoring</h3>

  <v-card variant="outlined" class="mb-4">
    <v-card-text>
      <v-form @submit.prevent="applyFilters">
        <v-row>
          <v-col cols="12" sm="6">
            <v-select
              v-model="historyRange"
              :items="ARR_RANGE_OPTION"
              :disabled="boolMetricsLoading || accessError !== null"
              label="Time Range"
              variant="outlined"
              hide-details />
          </v-col>

          <v-col cols="12" sm="6">
            <v-select
              v-model="strNetworkInterface"
              :items="instanceStatus?.network_interfaces ?? []"
              :disabled="boolMetricsLoading || !instanceStatus?.network_interfaces.length"
              label="Network Interface"
              variant="outlined"
              hide-details />
          </v-col>
        </v-row>

        <div class="d-flex justify-end mt-4">
          <v-btn
            type="submit"
            color="primary"
            variant="tonal"
            :disabled="boolMetricsLoading || accessError !== null">
            Apply
          </v-btn>
        </div>
      </v-form>
    </v-card-text>
  </v-card>

  <v-alert v-if="requestError" type="error" variant="tonal" class="mb-4" role="alert">
    {{ requestError.message }}
    <p v-if="instanceStatus" class="mt-2">
      Previously loaded metrics are shown and may be out of date.
    </p>
  </v-alert>

  <p v-if="strUpdatedAt" class="text-body-2 text-medium-emphasis mb-3">
    Updated at {{ formatDateTime(strUpdatedAt, strTimeZone) }}
  </p>

  <v-alert v-if="instanceStatus && !instanceStatus.configured" type="info" variant="tonal">
    Host monitoring is not configured.
  </v-alert>

  <template v-else-if="instanceStatus">
    <h4 class="text-subtitle-1 mb-2">Current Metrics</h4>
    <p class="text-body-2 text-medium-emphasis mb-3">
      Collected at {{ formatDateTime(instanceStatus.collected_at, strTimeZone) }}
    </p>

    <v-alert
      v-if="!instanceStatus.collected_at"
      type="warning"
      variant="tonal"
      class="mb-4">
      Current host metrics are unavailable. Earlier samples may still be shown below.
    </v-alert>

    <v-row class="mb-4" :aria-busy="boolMetricsLoading">
      <v-col v-for="metric in arrCurrentMetric" :key="metric.title" cols="12" sm="6" lg="3">
        <v-card variant="outlined" height="100%">
          <v-card-text>
            <p class="text-body-2 text-medium-emphasis mb-2">{{ metric.title }}</p>
            <p class="text-h5">{{ metric.value }}</p>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <h4 class="text-subtitle-1 mb-2">
      History · {{ MAP_RANGE_LABEL[instanceStatus.range] }}
    </h4>
    <p class="text-body-2 text-medium-emphasis mb-4">
      Each point shows the highest sampled value in a
      {{ instanceStatus.interval_seconds / 60 }}-minute interval. CPU and network values are
      averages between the latest two samples, usually one minute apart.
    </p>

    <v-row :aria-busy="boolMetricsLoading">
      <v-col cols="12" lg="6">
        <v-card variant="outlined">
          <v-card-title>CPU &amp; Memory</v-card-title>

          <v-card-text>
            <v-sheet
              v-if="boolHasUsageHistory"
              height="280"
              color="transparent"
              class="position-relative">
              <Line
                :data="usageChartData"
                :options="usageChartOptions"
                role="img"
                aria-label="CPU and memory usage over time" />
            </v-sheet>
            <p v-else class="text-body-2 text-medium-emphasis py-4">
              No CPU or memory samples are available for this range.
            </p>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" lg="6">
        <v-card variant="outlined">
          <v-card-title>
            Network{{
              instanceStatus.network_interface
                ? ` · ${instanceStatus.network_interface}`
                : ""
            }}
          </v-card-title>

          <v-card-text>
            <v-sheet
              v-if="boolHasNetworkHistory"
              height="280"
              color="transparent"
              class="position-relative">
              <Line
                :data="networkChartData"
                :options="networkChartOptions"
                role="img"
                aria-label="Network receive and send rates over time" />
            </v-sheet>
            <p v-else class="text-body-2 text-medium-emphasis py-4">
              No network samples are available for this range.
            </p>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </template>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";
import { useTheme } from "vuetify";
import { Line } from "vue-chartjs";
import {
  Chart as ChartJS,
  LineElement,
  PointElement,
  CategoryScale,
  LinearScale,
  Legend,
  type ChartData,
  type ChartOptions,
} from "chart.js";

import { useSessionStore } from "@/stores/sessionStore";

import { type ApiError, getApiError } from "@/api/errors";
import { getInstanceSummary, getInstanceStatus } from "@/api/instanceStatus";
import {
  type InstanceHealthStatus,
  type InstanceComponent,
  type InstanceSummaryResponse,
  type ServiceState,
  ARR_INSTANCE_HISTORY_RANGE,
  type InstanceHistoryRange,
  type InstanceStatusResponse,
} from "@/api/generated/browserApi";

import { formatDateTime, formatDateTimeInput, formatFileSize } from "@/app/formatters";

ChartJS.register(LineElement, PointElement, CategoryScale, LinearScale, Legend);

const MAP_SERVICE_STATE_LABEL: Record<ServiceState, string> = {
  normal: "Normal",
  maintenance: "Maintenance",
};
const MAP_COMPONENT_LABEL: Record<InstanceComponent, string> = {
  database: "Database",
  scheduler: "Scheduler",
  email: "Email",
  cleanup: "Cleanup",
  backup: "Backup",
};
const MAP_STATUS_LABEL: Record<InstanceHealthStatus, string> = {
  healthy: "Healthy",
  warning: "Warning",
  error: "Error",
  unknown: "Unknown",
};
const MAP_STATUS_COLOR: Record<InstanceHealthStatus, string> = {
  healthy: "success",
  warning: "warning",
  error: "error",
  unknown: "secondary",
};

const MAP_RANGE_LABEL: Record<InstanceHistoryRange, string> = {
  "1h": "Last Hour",
  "24h": "Last 24 Hours",
  "7d": "Last 7 Days",
  "15d": "Last 15 Days",
};
const ARR_RANGE_OPTION = ARR_INSTANCE_HISTORY_RANGE.map((value) => ({
  title: MAP_RANGE_LABEL[value],
  value,
}));

const sessionStore = useSessionStore();
const theme = useTheme();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const historyRange = ref<InstanceHistoryRange>("24h");
const strNetworkInterface = ref<string | null>(null);
let appliedFilters = {
  range: historyRange.value,
  networkInterface: strNetworkInterface.value,
};

const instanceSummary = shallowRef<InstanceSummaryResponse | null>(null);
const summaryError = shallowRef<ApiError | null>(null);
const boolSummaryLoading = ref(false);
let intSummaryRevision = 0;

const instanceStatus = shallowRef<InstanceStatusResponse | null>(null);
const requestError = shallowRef<ApiError | null>(null);
const strUpdatedAt = ref<string | null>(null);
const boolMetricsLoading = ref(false);
let intRequestRevision = 0;

const accessError = shallowRef<ApiError | null>(null);
const boolLoading = computed(() => boolSummaryLoading.value || boolMetricsLoading.value);

const arrCurrentMetric = computed(() => {
  const metrics = instanceStatus.value?.current;
  return [
    {
      title: "CPU",
      value: metrics?.cpu_percent == null ? "—" : `${metrics.cpu_percent.toFixed(2)}%`,
    },
    {
      title: "Memory",
      value:
        metrics?.memory_percent == null ? "—" : `${metrics.memory_percent.toFixed(2)}%`,
    },
    {
      title: "Network Receive Rate",
      value: formatThroughput(metrics?.network_receive_bytes_per_second ?? null),
    },
    {
      title: "Network Send Rate",
      value: formatThroughput(metrics?.network_transmit_bytes_per_second ?? null),
    },
  ];
});

const arrHistory = computed(() => instanceStatus.value?.history ?? []);
const arrChartLabel = computed(() =>
  arrHistory.value.map((sample) =>
    formatDateTimeInput(sample.timestamp, strTimeZone.value).replace("T", " "),
  ),
);
const boolHasUsageHistory = computed(() =>
  arrHistory.value.some(
    (sample) => sample.cpu_percent !== null || sample.memory_percent !== null,
  ),
);
const boolHasNetworkHistory = computed(() =>
  arrHistory.value.some(
    (sample) =>
      sample.network_receive_bytes_per_second !== null ||
      sample.network_transmit_bytes_per_second !== null,
  ),
);

const usageChartData = computed<ChartData<"line">>(() => ({
  labels: arrChartLabel.value,
  datasets: [
    {
      label: "CPU",
      data: arrHistory.value.map((sample) => sample.cpu_percent),
      borderColor: theme.current.value.colors.primary,
      spanGaps: false,
    },
    {
      label: "Memory",
      data: arrHistory.value.map((sample) => sample.memory_percent),
      borderColor: theme.current.value.colors.secondary,
      spanGaps: false,
    },
  ],
}));
const networkChartData = computed<ChartData<"line">>(() => ({
  labels: arrChartLabel.value,
  datasets: [
    {
      label: "Received",
      data: arrHistory.value.map((sample) => sample.network_receive_bytes_per_second),
      borderColor: theme.current.value.colors.primary,
      spanGaps: false,
    },
    {
      label: "Sent",
      data: arrHistory.value.map((sample) => sample.network_transmit_bytes_per_second),
      borderColor: theme.current.value.colors.secondary,
      spanGaps: false,
    },
  ],
}));
const usageChartOptions = computed(() => getChartOptions(true));
const networkChartOptions = computed(() => getChartOptions(false));

function formatStorageBytes(bytes: number | null): string {
  return bytes === null ? "—" : formatFileSize(bytes);
}

function formatThroughput(value: number | null): string {
  return value === null ? "—" : `${formatFileSize(Math.round(value))}/s`;
}

function getChartOptions(percent: boolean): ChartOptions<"line"> {
  const strTextColor = theme.current.value.colors["on-surface"];
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    events: [],
    elements: { point: { radius: 1.5 }, line: { borderWidth: 2, tension: 0 } },
    plugins: { legend: { labels: { color: strTextColor }, onClick: () => {} } },
    scales: {
      x: {
        ticks: { color: strTextColor, maxTicksLimit: 6, maxRotation: 0 },
        grid: { display: false },
      },
      y: {
        beginAtZero: true,
        max: percent ? 100 : undefined,
        ticks: {
          color: strTextColor,
          callback: (value) => (percent ? `${value}%` : formatThroughput(Number(value))),
        },
        grid: { color: theme.current.value.colors["surface-variant"] },
      },
    },
  };
}

async function clearAccessDeniedState(error: ApiError): Promise<void> {
  intSummaryRevision += 1;
  intRequestRevision += 1;
  instanceSummary.value = null;
  instanceStatus.value = null;
  strUpdatedAt.value = null;
  summaryError.value = null;
  requestError.value = null;
  boolSummaryLoading.value = false;
  boolMetricsLoading.value = false;
  accessError.value = error;
  if (error.statusCode === 403) await sessionStore.refreshSession();
}

async function loadInstanceSummary(): Promise<void> {
  const intCurrentRevision = ++intSummaryRevision;
  boolSummaryLoading.value = true;
  summaryError.value = null;

  try {
    const response = await getInstanceSummary();
    if (intCurrentRevision !== intSummaryRevision) return;
    instanceSummary.value = response;
  } catch (e) {
    if (intCurrentRevision !== intSummaryRevision) return;
    const error = getApiError(e);
    if ([401, 403].includes(error.statusCode)) {
      await clearAccessDeniedState(error);
    } else {
      summaryError.value = error;
    }
  } finally {
    if (intCurrentRevision === intSummaryRevision) boolSummaryLoading.value = false;
  }
}

async function loadInstanceStatus(): Promise<void> {
  const intCurrentRevision = ++intRequestRevision;
  boolMetricsLoading.value = true;
  requestError.value = null;

  try {
    const response = await getInstanceStatus(
      appliedFilters.range,
      appliedFilters.networkInterface,
    );
    if (intCurrentRevision !== intRequestRevision) return;
    instanceStatus.value = response;
    strUpdatedAt.value = new Date().toISOString();
    historyRange.value = response.range;
    strNetworkInterface.value = response.network_interface;
    appliedFilters = {
      range: response.range,
      networkInterface: response.network_interface,
    };
  } catch (e) {
    if (intCurrentRevision !== intRequestRevision) return;
    const error = getApiError(e);
    if ([401, 403].includes(error.statusCode)) {
      await clearAccessDeniedState(error);
    } else {
      requestError.value = error;
    }
  } finally {
    if (intCurrentRevision === intRequestRevision) boolMetricsLoading.value = false;
  }
}

async function loadOverview(): Promise<void> {
  accessError.value = null;
  await Promise.all([loadInstanceSummary(), loadInstanceStatus()]);
}

function applyFilters(): void {
  appliedFilters = {
    range: historyRange.value,
    networkInterface: strNetworkInterface.value,
  };
  void loadInstanceStatus();
}

onMounted(() => void loadOverview());
onBeforeUnmount(() => {
  intSummaryRevision += 1;
  intRequestRevision += 1;
});
</script>

<style scoped></style>
