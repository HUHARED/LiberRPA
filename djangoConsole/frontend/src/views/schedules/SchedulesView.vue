<!-- FileName: SchedulesView.vue -->
<template>
  <div class="d-flex align-center flex-wrap ga-3 mb-4">
    <h1 class="text-h5">Schedules</h1>
    <v-spacer />
    <v-btn v-if="boolCanCreate" color="primary" variant="tonal" @click="boolNew = true">
      New Schedule
    </v-btn>
    <v-btn variant="tonal" :loading="boolLoading" @click="load()">Refresh</v-btn>
  </div>
  <v-card variant="elevated" class="mb-4">
    <v-card-text>
      <form @submit.prevent="apply">
        <v-row>
          <v-col cols="12" md="4">
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
          <v-col cols="12" md="4">
            <v-text-field v-model="filters.name" label="Name" hide-details />
          </v-col>
          <v-col cols="12" md="4">
            <v-text-field v-model="filters.projectName" label="Project" hide-details />
          </v-col>
          <v-col cols="12" md="6">
            <v-select
              v-model="filters.enabled"
              :items="ARR_ENABLED"
              label="Enabled"
              hide-details />
          </v-col>
          <v-col cols="12" md="6">
            <v-autocomplete
              v-model="filters.targetId"
              :items="arrTarget"
              item-title="title"
              item-value="id"
              label="Target"
              clearable
              hide-details
              :loading="boolTargetsLoading" />
          </v-col>
        </v-row>
        <div class="d-flex ga-2 mt-4">
          <v-btn type="submit" color="primary" variant="tonal">Apply</v-btn>
          <v-btn variant="tonal" @click="clearFilters">Reset Filters</v-btn>
        </div>
      </form>
    </v-card-text>
  </v-card>
  <v-alert v-if="strError" type="error" variant="tonal" class="mb-4">
    {{ strError }}
  </v-alert>
  <v-card variant="outlined">
    <v-data-table-server
      :headers="ARR_HEADER"
      :items="page?.schedules ?? []"
      :items-length="page?.total_count ?? 0"
      :items-per-page="50"
      :loading="boolLoading"
      disable-sort
      hide-default-footer>
      <template #item.name="{ item }">
        <RouterLink
          :to="{ name: 'schedule-details', params: { scheduleId: item.id } }"
          class="text-primary text-decoration-none">
          {{ item.name }}
        </RouterLink>
      </template>
      <template #item.department="{ item }">{{ item.department.path }}</template>
      <template #item.cron="{ item }">
        <p>{{ describeCron(item.cron) }}</p>
        <span class="text-caption">{{ item.time_zone }}</span>
      </template>
      <template #item.target="{ item }">
        {{
          item.executor_group?.name ||
          item.executors?.map((executor) => executor.name).join(", ") ||
          (item.group_id ? "Executor Group" : `${item.executor_ids.length} Executors`)
        }}
      </template>
      <template #item.enabled="{ item }">
        <v-switch
          :model-value="item.enabled"
          true-icon="mdi-flash"
          hide-details
          density="compact"
          :disabled="!item.can_manage || boolLoading || strChangingId === item.id"
          :loading="strChangingId === item.id"
          @update:model-value="toggle(item, !!$event)" />
      </template>
      <template #item.created_by="{ item }">
        {{
          item.created_by ? `${item.created_by.username} (${item.created_by.email})` : "—"
        }}
      </template>
      <template #item.actions="{ item }">
        <div class="d-flex align-center ga-1">
          <v-btn
            v-if="item.can_manage"
            v-tooltip:bottom="'Edit'"
            size="small"
            variant="text"
            aria-label="Edit"
            icon="mdi-pencil-outline"
            @click="strEditId = item.id" />
        </div>
      </template>
      <template #no-data>No schedules match the current filters.</template>
    </v-data-table-server>
    <v-divider />
    <div class="d-flex align-center justify-space-between pa-3">
      <span>{{ page?.total_count ?? 0 }} schedules</span>
      <v-pagination
        v-if="page && page.total_pages > 1"
        :model-value="page.page"
        :length="page.total_pages"
        :total-visible="5"
        :disabled="boolLoading"
        @update:model-value="load" />
    </div>
  </v-card>
  <ScheduleFormDialog
    v-if="boolNew || strEditId"
    :schedule-id="strEditId ?? undefined"
    @close="closeForm"
    @saved="saved" />
</template>
<script setup lang="ts">
import { shallowRef, computed, onMounted, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import cronstrue from "cronstrue";

import { getExecutorList } from "@/api/executors";
import { getExecutorGroupList } from "@/api/executorGroups";

import ScheduleFormDialog from "@/components/schedules/ScheduleFormDialog.vue";

import {
  type ScheduleListEntry,
  type SchedulePage,
  type ScheduleFilters,
  getSchedules,
  setScheduleEnabled,
} from "@/api/schedules";
import { getApiError } from "@/api/errors";

import { useSessionStore } from "@/stores/sessionStore";

const ARR_HEADER = [
  { title: "Name", key: "name" },
  { title: "Department", key: "department" },
  { title: "Project", key: "project_name" },
  { title: "Version", key: "project_version" },
  { title: "Run Time", key: "cron" },
  { title: "Target", key: "target" },
  { title: "Enabled", key: "enabled" },
  { title: "Created By", key: "created_by" },
  { title: "Notes", key: "notes" },
  { title: "Actions", key: "actions" },
];
const ARR_ENABLED = [
  { title: "All", value: "" },
  { title: "Enabled", value: "true" },
  { title: "Disabled", value: "false" },
];
const sessionStore = useSessionStore();
const route = useRoute();
const boolCanCreate = computed(
  () =>
    sessionStore.access?.is_org_admin ||
    sessionStore.access?.departments.some((department) => department.role === "developer"),
);

function emptyFilters(): ScheduleFilters {
  return { name: "", departmentIds: [], projectName: "", enabled: "", targetId: "" };
}
const arrTarget = ref<{ id: string; title: string }[]>([]);
const boolTargetsLoading = ref(false);
const filters = ref(emptyFilters());
if (typeof route.query.department_id === "string")
  filters.value.departmentIds = [route.query.department_id];
let appliedFilters = { ...filters.value, departmentIds: [...filters.value.departmentIds] };
const page = shallowRef<SchedulePage | null>(null);
const boolNew = ref(false);
const strEditId = ref<string | null>(null);
const strChangingId = ref("");
const boolLoading = ref(false);
const strError = ref("");

let intLoadRevision = 0;

function describeCron(value: string): string {
  try {
    return cronstrue.toString(value, { use24HourTimeFormat: true });
  } catch {
    return value;
  }
}

async function loadTargets(): Promise<void> {
  boolTargetsLoading.value = true;
  try {
    const arrResult: { id: string; title: string }[] = [];
    const arrPages = await Promise.all([
      getExecutorList({ name: "", departmentIds: [], dispatchStates: [] }, 1),
      getExecutorGroupList({ name: "", departmentIds: [] }, 1),
    ]);
    const executorPage = arrPages[0];
    const groupPage = arrPages[1];
    arrResult.push(
      ...executorPage.executors.map((entry) => ({
        id: entry.id,
        title: `Executor: ${entry.name} (${entry.department.path})`,
      })),
    );
    arrResult.push(
      ...groupPage.executor_groups.map((entry) => ({
        id: entry.id,
        title: `Group: ${entry.name} (${entry.department.path})`,
      })),
    );
    for (let intPage = 2; intPage <= executorPage.total_pages; intPage++) {
      const result = await getExecutorList(
        { name: "", departmentIds: [], dispatchStates: [] },
        intPage,
      );
      arrResult.push(
        ...result.executors.map((entry) => ({
          id: entry.id,
          title: `Executor: ${entry.name} (${entry.department.path})`,
        })),
      );
    }
    for (let intPage = 2; intPage <= groupPage.total_pages; intPage++) {
      const result = await getExecutorGroupList({ name: "", departmentIds: [] }, intPage);
      arrResult.push(
        ...result.executor_groups.map((entry) => ({
          id: entry.id,
          title: `Group: ${entry.name} (${entry.department.path})`,
        })),
      );
    }
    arrTarget.value = arrResult;
  } catch (e) {
    strError.value = getApiError(e).message;
  } finally {
    boolTargetsLoading.value = false;
  }
}

async function load(pageNumber = page.value?.page ?? 1): Promise<void> {
  const intRevision = ++intLoadRevision;
  boolLoading.value = true;
  strError.value = "";
  try {
    const response = await getSchedules(appliedFilters, pageNumber);
    if (intRevision === intLoadRevision) page.value = response;
  } catch (e) {
    if (intRevision === intLoadRevision) strError.value = getApiError(e).message;
  } finally {
    if (intRevision === intLoadRevision) boolLoading.value = false;
  }
}

function apply(): void {
  appliedFilters = { ...filters.value, departmentIds: [...filters.value.departmentIds] };
  void load(1);
}

function clearFilters(): void {
  filters.value = emptyFilters();
  apply();
}

async function toggle(schedule: ScheduleListEntry, enabled: boolean): Promise<void> {
  strChangingId.value = schedule.id;
  strError.value = "";
  try {
    await setScheduleEnabled(schedule.id, enabled);
    schedule.enabled = enabled;
  } catch (e) {
    strError.value = getApiError(e).message;
  } finally {
    strChangingId.value = "";
  }
}

function closeForm(): void {
  boolNew.value = false;
  strEditId.value = null;
}

function saved(): void {
  closeForm();
  void load();
}

onMounted(() => {
  void load();
  void loadTargets();
});
</script>
<style scoped></style>
