<!-- FileName: JobQueueView.vue -->
<template>
  <div class="d-flex align-center flex-wrap ga-3 mb-4">
    <h1 class="text-h5">Job Queue</h1>
    <v-spacer />
    <v-btn
      variant="tonal"
      prepend-icon="mdi-refresh"
      :loading="boolLoading"
      @click="load()">
      Refresh
    </v-btn>
  </div>

  <v-tabs :model-value="boolFinished" class="mb-4" @update:model-value="changeTab">
    <v-tab :value="false">Active</v-tab>
    <v-tab :value="true">Finished</v-tab>
  </v-tabs>

  <v-card variant="elevated" class="mb-4">
    <v-card-text>
      <form @submit.prevent="apply">
        <v-row>
          <v-col cols="12" :md="boolFinished ? 4 : 3">
            <v-select
              v-model="filters.departmentIds"
              :items="sessionStore.access?.departments ?? []"
              item-title="path"
              item-value="id"
              label="Department"
              variant="underlined"
              multiple
              chips
              hide-details />
          </v-col>

          <v-col cols="12" :md="boolFinished ? 4 : 3">
            <v-text-field
              v-model="filters.scheduleName"
              label="Schedule"
              variant="underlined"
              hide-details />
          </v-col>

          <v-col cols="12" :md="boolFinished ? 4 : 3">
            <v-text-field
              v-model="filters.projectName"
              label="Project"
              variant="underlined"
              hide-details />
          </v-col>

          <v-col v-if="!boolFinished" cols="12" md="3">
            <v-select
              v-model="filters.states"
              :items="
                ARR_ACTIVE_JOB_STATE.map((value) => ({
                  value,
                  title: JOB_STATE_LABELS[value],
                }))
              "
              label="Status"
              variant="underlined"
              multiple
              chips
              hide-details />
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
    <p v-if="page">The displayed results may be out of date.</p>
  </v-alert>

  <TimeZoneHint :time-zone="strTimeZone" :updated-at="strUpdatedAt" />

  <v-card variant="outlined">
    <v-data-table-server
      :headers="arrHeader"
      :items="page?.jobs ?? []"
      :items-length="page?.total_count ?? 0"
      :items-per-page="page?.page_size ?? INT_LIST_PAGE_SIZE"
      :loading="boolLoading"
      disable-sort
      hide-default-footer>
      <template #item.schedule_name="{ item }">
        <RouterLink
          v-if="item.can_view_schedule"
          :to="{ name: 'schedule', params: { scheduleId: item.schedule_id } }"
          class="text-primary text-decoration-none">
          {{ item.schedule_name }}
        </RouterLink>
        <span v-else>{{ item.schedule_name || "—" }}</span>
      </template>

      <template #item.target_name="{ item }">
        <RouterLink
          v-if="item.can_view_target"
          :to="{
            name:
              item.target_type === JobTargetType.Group
                ? 'executor-group-details'
                : 'executor-details',
            params:
              item.target_type === JobTargetType.Group
                ? { groupId: item.target_id }
                : { executorId: item.target_id },
          }"
          class="text-primary text-decoration-none">
          {{ item.target_name }}
        </RouterLink>
        <span v-else>{{ item.target_name }}</span>
        <template v-if="item.target_type === JobTargetType.Group && item.executor_id">
          →
          <RouterLink
            v-if="item.can_view_executor"
            :to="{ name: 'executor-details', params: { executorId: item.executor_id } }"
            class="text-primary text-decoration-none">
            {{ item.executor_name }}
          </RouterLink>
          <span v-else>{{ item.executor_name }}</span>
        </template>
      </template>

      <template #item.priority="{ item }">{{ PRIORITY_LABELS[item.priority] }}</template>

      <template #item.queued_at="{ item }">
        {{ formatDateTime(item.queued_at, strTimeZone, false) }}
      </template>

      <template #item.ended_at="{ item }">
        {{ formatDateTime(item.ended_at, strTimeZone, false) }}
      </template>

      <template #item.state="{ item }">
        <v-chip
          :border="`${JOB_STATE_COLORS[item.state]} thin opacity-25`"
          :color="JOB_STATE_COLORS[item.state]"
          :text="JOB_STATE_LABELS[item.state]"
          variant="text"
          size="x-small" />
      </template>

      <template #item.reason="{ item }">
        <p class="text-pre-wrap text-break my-2">{{ item.reason || "—" }}</p>
      </template>

      <template #item.actions="{ item }">
        <div class="d-flex align-center ga-1">
          <v-btn
            v-tooltip:bottom="'View Job Details'"
            :to="{
              name: 'job-details',
              params: { jobId: item.id },
              query: { ...route.query, from: 'job-queue' },
            }"
            size="small"
            variant="text"
            aria-label="View Job Details"
            icon="mdi-eye-outline" />

          <JobActions :job="item" icon-only @updated="load()" @error="strError = $event" />
        </div>
      </template>

      <template #no-data>
        No {{ boolFinished ? "finished" : "active" }} Jobs match the current filters.
      </template>
    </v-data-table-server>

    <v-divider />

    <div class="d-flex justify-space-between align-center pa-3">
      <span>{{ page?.total_count ?? 0 }} Jobs</span>
      <v-pagination
        v-if="page && page.total_pages > 1"
        :model-value="page.page"
        :length="page.total_pages"
        :total-visible="5"
        :disabled="boolLoading"
        @update:model-value="changePage" />
    </div>
  </v-card>
</template>

<script setup lang="ts">
import { shallowRef, computed, onBeforeUnmount, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import type { DataTableHeader } from "vuetify";

import TimeZoneHint from "@/components/common/TimeZoneHint.vue";
import JobActions from "@/components/runs/JobActions.vue";

import { ARR_ACTIVE_JOB_STATE, getJobs, type JobPage, type JobFilters } from "@/api/runs";
import { getApiError } from "@/api/errors";
import { INT_LIST_PAGE_SIZE, JobTargetType, JobState } from "@/api/generated/browserApi";

import { PRIORITY_LABELS, JOB_STATE_LABELS, JOB_STATE_COLORS } from "@/app/runLabels";
import { formatDateTime } from "@/app/formatters";

import { useSessionStore } from "@/stores/sessionStore";
import { useRetryDelay } from "@/composables/useRetryDelay";
import { useExecutionRefresh } from "@/composables/useExecutionRefresh";

const sessionStore = useSessionStore();
const route = useRoute();
const router = useRouter();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
const boolFinished = computed(
  () =>
    route.query.tab === JobState.Finished ||
    [route.query.state].flat().includes(JobState.Finished),
);

const arrHeader = computed<DataTableHeader[]>(() => [
  { title: "Schedule", key: "schedule_name" },
  { title: "Project Name", key: "project_name" },
  { title: "Project Version", key: "project_version" },
  { title: "Target", key: "target_name" },
  ...(!boolFinished.value ? [{ title: "Priority", key: "priority" }] : []),
  { title: "Queued At", key: "queued_at" },
  ...(boolFinished.value ? [{ title: "Ended At", key: "ended_at" }] : []),
  { title: "Status", key: "state" },
  ...(boolFinished.value
    ? [{ title: "Reason", key: "reason", width: 320, maxWidth: 360 }]
    : []),
  { title: "Actions", key: "actions" },
]);

function emptyFilters(): JobFilters {
  return {
    departmentIds: [],
    projectName: "",
    scheduleName: "",
    states: [],
  };
}

const filters = ref(emptyFilters());
const appliedFilters = computed<JobFilters>(() => ({
  departmentIds: [route.query.department_id]
    .flat()
    .filter((value): value is string => typeof value === "string"),
  projectName: typeof route.query.project_name === "string" ? route.query.project_name : "",
  scheduleName:
    typeof route.query.schedule_name === "string" ? route.query.schedule_name : "",
  states: ARR_ACTIVE_JOB_STATE.filter((state) =>
    [route.query.state].flat().includes(state),
  ),
}));

const page = shallowRef<JobPage | null>(null);
const strUpdatedAt = ref<string | null>(null);
const boolLoading = ref(false);
const strError = ref("");
const { intRetrySeconds, setRetryDelay } = useRetryDelay();
let intLoadRevision = 0;
const { beginRefresh, requestRefresh } = useExecutionRefresh(
  load,
  boolLoading,
  intRetrySeconds,
);

async function load(): Promise<void> {
  if (!beginRefresh()) return;

  const intRevision = ++intLoadRevision;
  boolLoading.value = true;
  strError.value = "";
  try {
    const response = await getJobs(
      {
        ...appliedFilters.value,
        states: boolFinished.value ? [JobState.Finished] : appliedFilters.value.states,
      },
      Number(route.query.page) || 1,
    );
    if (intRevision === intLoadRevision) {
      page.value = response;
      strUpdatedAt.value = new Date().toISOString();
      setRetryDelay(0);
    }
  } catch (e) {
    if (intRevision === intLoadRevision) {
      const error = getApiError(e);
      strError.value = error.message;
      if (error.statusCode === 403 || error.statusCode === 404) {
        page.value = null;
        strUpdatedAt.value = null;
      }
      if (error.statusCode === 429 && (error.retryAfterSeconds ?? 0) > 0) {
        setRetryDelay(error.retryAfterSeconds);
        requestRefresh();
      }
    }
  } finally {
    boolLoading.value = false;
  }
}

async function changePage(value: number): Promise<void> {
  await router.replace({ query: { ...route.query, page: String(value) } });
}

async function changeTab(value: unknown): Promise<void> {
  await router.replace({
    query: {
      ...route.query,
      tab: value === true ? JobState.Finished : undefined,
      state: appliedFilters.value.states,
      page: undefined,
    },
  });
}

async function apply(): Promise<void> {
  const location = {
    name: "job-queue",
    query: {
      tab: boolFinished.value ? JobState.Finished : undefined,
      department_id: filters.value.departmentIds,
      project_name: filters.value.projectName.trim() || undefined,
      schedule_name: filters.value.scheduleName.trim() || undefined,
      state: filters.value.states,
    },
  };
  if (router.resolve(location).fullPath === route.fullPath) await load();
  else await router.replace(location);
}

function clearFilters(): void {
  filters.value = emptyFilters();
  void apply();
}

watch(
  [appliedFilters, boolFinished, () => route.query.page],
  ([currentFilters], [previousFilters]) => {
    if (route.name !== "job-queue") return;
    if (JSON.stringify(currentFilters) !== JSON.stringify(previousFilters)) {
      filters.value = {
        ...currentFilters,
        departmentIds: [...currentFilters.departmentIds],
        states: [...currentFilters.states],
      };
    }
    intLoadRevision += 1;
    page.value = null;
    strUpdatedAt.value = null;
    void load();
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  intLoadRevision += 1;
});
</script>

<style scoped></style>
