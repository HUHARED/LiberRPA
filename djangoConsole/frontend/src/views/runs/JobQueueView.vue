<!-- FileName: JobQueueView.vue -->
<template>
  <div class="d-flex align-center flex-wrap ga-3 mb-4">
    <h1 class="text-h5">Job Queue</h1>
    <v-spacer />
    <v-btn variant="tonal" :loading="boolLoading" @click="load()">Refresh</v-btn>
  </div>
  <v-card variant="outlined" class="mb-4">
    <v-card-text>
      <form @submit.prevent="apply">
        <v-row>
          <v-col cols="12" md="3">
            <v-select
              v-model="filters.departmentIds"
              :items="sessionStore.access?.departments ?? []"
              item-title="path"
              item-value="id"
              label="Department"
              multiple
              chips
              hide-details />
          </v-col>
          <v-col cols="12" md="3">
            <v-text-field v-model="filters.scheduleName" label="Schedule" hide-details />
          </v-col>
          <v-col cols="12" md="3">
            <v-text-field v-model="filters.projectName" label="Project" hide-details />
          </v-col>
          <v-col cols="12" md="3">
            <v-select
              v-model="filters.states"
              :items="
                ARR_JOB_STATE.map((value) => ({ value, title: JOB_STATE_LABELS[value] }))
              "
              label="Status"
              multiple
              chips
              hide-details />
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
    <p v-if="page">The displayed results may be out of date.</p>
  </v-alert>
  <p class="text-body-2 text-medium-emphasis mb-3">
    Active Jobs only · Time zone: {{ strTimeZone }}
  </p>
  <v-card variant="outlined">
    <v-data-table-server
      :headers="ARR_HEADER"
      :items="page?.jobs ?? []"
      :items-length="page?.total_count ?? 0"
      :items-per-page="50"
      :loading="boolLoading"
      disable-sort
      hide-default-footer>
      <template #item.schedule_name="{ item }">
        <RouterLink
          v-if="item.schedule_id"
          :to="{ name: 'schedule-details', params: { scheduleId: item.schedule_id } }">
          {{ item.schedule_name }}
        </RouterLink>
        <span v-else>—</span>
      </template>
      <template #item.target_name="{ item }">
        <RouterLink
          :to="{
            name:
              item.target_type === 'group' ? 'executor-group-details' : 'executor-details',
            params:
              item.target_type === 'group'
                ? { groupId: item.target_id }
                : { executorId: item.target_id },
          }">
          {{ item.target_name }}
        </RouterLink>
        <template v-if="item.target_type === 'group' && item.executor_id">
          →
          <RouterLink
            :to="{ name: 'executor-details', params: { executorId: item.executor_id } }">
            {{ item.executor_name }}
          </RouterLink>
        </template>
      </template>
      <template #item.priority="{ item }">{{ PRIORITY_LABELS[item.priority] }}</template>
      <template #item.queued_at="{ item }">
        {{ formatDateTime(item.queued_at, strTimeZone) }}
      </template>
      <template #item.state="{ item }">
        <v-chip size="small" :color="item.state === 'needs_review' ? 'warning' : undefined">
          {{ JOB_STATE_LABELS[item.state] }}
        </v-chip>
      </template>
      <template #item.actions="{ item }">
        <div class="d-flex align-center">
          <v-btn
            :to="{ name: 'job-details', params: { jobId: item.id } }"
            size="small"
            variant="text">
            View
          </v-btn>
          <JobActions :job="item" @updated="load()" @error="strError = $event" />
        </div>
      </template>
      <template #no-data>No active Jobs match the current filters.</template>
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
        @update:model-value="load" />
    </div>
  </v-card>
</template>
<script setup lang="ts">
import { shallowRef, computed, onBeforeUnmount, onMounted, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import JobActions from "@/components/runs/JobActions.vue";
import { ARR_JOB_STATE, getJobs, type JobPage, type JobFilters } from "@/api/runs";
import { getApiError } from "@/api/errors";
import { PRIORITY_LABELS, JOB_STATE_LABELS } from "@/app/runLabels";
import { formatDateTime } from "@/app/formatters";
import { useSessionStore } from "@/stores/sessionStore";
const ARR_HEADER = [
  { title: "Schedule", key: "schedule_name" },
  { title: "Project", key: "project_name" },
  { title: "Version", key: "project_version" },
  { title: "Target", key: "target_name" },
  { title: "Priority", key: "priority" },
  { title: "Queued At", key: "queued_at" },
  { title: "Status", key: "state" },
  { title: "Actions", key: "actions" },
];
const sessionStore = useSessionStore();
const route = useRoute();
const strTimeZone = computed(() => sessionStore.session?.user.time_zone ?? "UTC");
function emptyFilters(): JobFilters {
  return {
    departmentIds: [],
    projectName: "",
    scheduleName: "",
    states: [],
  };
}
const filters = ref(emptyFilters());
const initialState = ARR_JOB_STATE.find((state) => state === route.query.state);
if (initialState) filters.value.states = [initialState];
if (typeof route.query.department_id === "string")
  filters.value.departmentIds = [route.query.department_id];
let appliedFilters = {
  ...filters.value,
  departmentIds: [...filters.value.departmentIds],
  states: [...filters.value.states],
};
const page = shallowRef<JobPage | null>(null);
const boolLoading = ref(false);
const strError = ref("");
let refreshTimer: ReturnType<typeof setInterval> | undefined;
let intLoadRevision = 0;
async function load(pageNumber = page.value?.page ?? 1): Promise<void> {
  const intRevision = ++intLoadRevision;
  boolLoading.value = true;
  strError.value = "";
  try {
    const response = await getJobs(appliedFilters, pageNumber);
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
    states: [...filters.value.states],
  };
  void load(1);
}
function clearFilters(): void {
  filters.value = emptyFilters();
  apply();
}
onMounted(() => {
  void load();
  refreshTimer = setInterval(() => {
    if (!document.hidden && !boolLoading.value) void load();
  }, 10000);
});
onBeforeUnmount(() => clearInterval(refreshTimer));
</script>
<style scoped></style>
